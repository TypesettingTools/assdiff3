#!/bin/env python3

import argparse
import collections
import collections.abc
import heapq
import io
import re
import sys

parser = argparse.ArgumentParser(description='Three-way merge of ASS files')
parser.add_argument('myfile', help="The locally changed file")
parser.add_argument('oldfile', help="The parent file that both files diverged from")
parser.add_argument('yourfile', help="The remotely changed file")
parser.add_argument('--output', '-o', help="File to output to")
parser.add_argument('--conflict-marker', choices=['diff3', 'description'], default='description',
                    help="Type of conflict marker to use: diff3-style markers or textual descriptions")
parser.add_argument('--conflict-marker-size', type=int, default=7,
                    help="Size of conflict marker when using diff3-style conflict markers")
parser.add_argument('--diff3', action='store_true', help="Use diff3-style three-way diffing")
parser.add_argument('--script-info', choices=['ours', 'theirs'], default='ours',
                    help="Whether to keep 'our' or 'their' changes for the script info and Aegisub project sections")
args = parser.parse_args()

CONFLICT_LINE = "Comment: 0,0:00:00.00,0:00:00.00,Default,,0,0,0,CONFLICT,{}"

CONFLICT_MARKERS = {
    "diff3": {
        "ours": "<" * args.conflict_marker_size,
        "ancestor": "|" * args.conflict_marker_size,
        "theirs": "=" * args.conflict_marker_size,
        "end": ">" * args.conflict_marker_size
    },
    "description": {
        "ours": "Start of own hunk",
        "ancestor": "End of own hunk; Start of common ancestor's hunk",
        "theirs": "End of {} hunk; Start of other hunk".format(
            "common ancestor's" if args.diff3 else "own"),
        "end": "End of other hunk"
    }
}

class ASSLine(collections.abc.Mapping):
    VALID_TYPES = None

    def __init__(self, line=None, fields=None, source_file=None):
        self.source_file = source_file

        if line is not None:
            line_type, line_data = line.split(": ", 1)
            field_values = line_data.split(",", len(self.FIELDS) - 1)
            if len(field_values) != len(self.FIELDS):
                raise ValueError("Malformed line: {}".format(line))

            self.fields = dict(zip(self.FIELDS, field_values))
            self.fields["Type"] = line_type
        elif fields is not None:
            self.fields = fields


        if self.VALID_TYPES is not None and self.Type not in self.VALID_TYPES:
            raise ValueError("Not a valid line type")

    @classmethod
    def merge(cls, a, parent, b):
        changed_a = {field: value for field, value in a.items()
                     if value != parent[field]}
        changed_b = {field: value for field, value in b.items()
                     if value != parent[field]}

        if len(changed_a.keys() & changed_b.keys()) > 0:
            return None

        return cls(fields={**parent, **changed_a, **changed_b}, source_file="?")

    def __str__(self):
        ordered_fields = [str(self[field]) for field in self.FIELDS]
        return f"{self.Type}: {','.join(ordered_fields)}"

    def __getattr__(self, key):
        return self.fields[key]

    def __getitem__(self, item):
        return getattr(self, item)

    def __len__(self):
        return len(self.fields) + 1

    def __iter__(self):
        yield "Type"
        yield from self.fields

class DialogueLine(ASSLine):
    FIELDS = ['Layer', 'Start', 'End', 'Style', 'Name', 'MarginL',
              'MarginR', 'MarginV', 'Effect', 'Text']
    VALID_TYPES = {"Dialogue", "Comment"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra_indices = []

        match = re.match(r"^\{((?:=\d+)+)\}(.*)$", self.fields["Text"])
        if match:
            self.extra_indices = list(map(int, match.group(1).split("=")[1:]))
            self.fields["Text"] = match.group(2)

    @property
    def Text(self):
        if len(self.extra_indices) > 0:
            return "{{={}}}{}".format("=".join(str(x) for x in self.extra_indices),
                                      self.fields["Text"])
        else:
            return self.fields["Text"]


class StyleLine(ASSLine):
    FIELDS = ['Name', 'Fontname', 'Fontsize', 'PrimaryColour', 'SecondaryColour',
              'OutlineColour', 'BackColour', 'Bold', 'Italic', 'Underline',
              'StrikeOut', 'ScaleX', 'ScaleY', 'Spacing', 'Angle', 'BorderStyle',
              'Outline', 'Shadow', 'Alignment', 'MarginL', 'MarginR', 'MarginV', 'Encoding']
    VALID_TYPES = {"Style"}

class DataLine(ASSLine):
    FIELDS = ["Id", "Key", "Value"]
    VALID_TYPES = {"Data"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["Id"] = int(self.fields["Id"])

class KeyValueLine(ASSLine):
    FIELDS = ["Value"]

SECTIONS = {
    "Script Info": KeyValueLine,
    "Aegisub Project Garbage": KeyValueLine,
    "V4+ Styles": StyleLine,
    "Events": DialogueLine,
    "Aegisub Extradata": DataLine
}

def parse_file(fname, indicator=None):
    sections = collections.defaultdict(list)
    current_section = "?"
    with open(fname, 'r', encoding='utf-8-sig') as f:
        for raw_line in f:
            line = raw_line.strip()
            section = re.match(r"^\[(.*)\]$", line)
            if section:
                current_section = section.group(1)
            elif len(line) > 0:
                factory = SECTIONS.get(current_section, lambda x, **kwargs: x)
                try:
                    sections[current_section].append(factory(line, source_file=indicator))
                except ValueError: # ignore unexpected lines
                    pass

    return sections

def merge_keyval(A, O, B):
    lines_to_map = lambda lines: collections.OrderedDict(
        (line.Type, line.Value) for line in lines)
    a_map = lines_to_map(A)
    o_map = lines_to_map(O)
    b_map = lines_to_map(B)

    a_changed = collections.OrderedDict((key, value) for key, value in a_map.items()
                                        if key not in o_map or o_map[key] != value)
    a_removed = {key for key in o_map if key not in a_map}
    b_changed = collections.OrderedDict((key, value) for key, value in b_map.items()
                                        if key not in o_map or o_map[key] != value)
    b_removed = {key for key in o_map if key not in b_map}

    if args.script_info == 'ours':
        first_removed, first_changed, second_removed, second_changed = \
            b_removed, b_changed, a_removed, a_changed
    else:
        first_removed, first_changed, second_removed, second_changed = \
            a_removed, a_changed, b_removed, b_changed

    for key in first_removed:
        o_map.pop(key, None)
    o_map.update(first_changed)
    for key in second_removed:
        o_map.pop(key, None)
    o_map.update(second_changed)

    return [KeyValueLine(fields={"Type": key, "Value": value})
            for key, value in o_map.items()]

def merge_extradata(mine, parent, their):
    extradata_to_id = {}
    id_to_extradata = {}
    largest_id = 0
    for f in (parent, mine, their):
        id_map = {}
        for data_line in f["Aegisub Extradata"]:
            original_id = data_line.Id
            if (data_line.Key, data_line.Value) in extradata_to_id:
                data_line.Id = extradata_to_id[(data_line.Key, data_line.Value)]
            else:
                if data_line.Id in id_to_extradata:
                    data_line.Id = largest_id + 1

                extradata_to_id[(data_line.Key, data_line.Value)] = data_line.Id
                id_to_extradata[data_line.Id] = data_line
                largest_id = max(largest_id, data_line.Id)

            id_map[original_id] = data_line.Id

        for dialogue_line in f["Events"]:
            dialogue_line.extra_indices = [id_map[i] for i in dialogue_line.extra_indices
                                           if i in id_map]

    return [id_to_extradata[i] for i in sorted(id_to_extradata)]


class LineMatcher:
    def __init__(self, a, b, memoizers=(lambda x: x,)):
        self.a = a
        self.b = b
        self.memoizers = memoizers
        self.index_maps = [{} for _ in self.memoizers]

        for i, line in enumerate(b):
            for imap, memoizer in zip(self.index_maps, self.memoizers):
                imap.setdefault(memoizer(line), []).append(i)

    def _lcs(self, ai, aj, bi, bj):
        longest_match = 0
        start_a, start_b = ai, bi
        match_lengths = {}
        for i in range(ai, aj):
            updated_match_lengths = {}
            line_a = self.a[i]
            b_matches = heapq.merge(
                *(imap.get(memoizer(line_a), [])
                  for imap, memoizer in zip(self.index_maps, self.memoizers)))

            for j in b_matches:
                if j < bi:
                    continue
                elif j >= bj:
                    break

                match_length = match_lengths.get(j - 1, 0) + 1
                updated_match_lengths[j] = match_length

                if match_length > longest_match:
                    longest_match = match_length
                    start_a = i - match_length + 1
                    start_b = j - match_length + 1
            match_lengths = updated_match_lengths

        return start_a, start_b, longest_match

    def find_matches(self):
        matches = []
        queue = collections.deque()
        queue.append((0, len(self.a), 0, len(self.b)))
        while len(queue) > 0:
            ai, aj, bi, bj = queue.popleft()
            if aj - ai <= 0 or bj - bi <= 0:
                continue

            match = self._lcs(ai, aj, bi, bj)
            start_a, start_b, match_length = match

            if match_length > 0:
                queue.append((ai, start_a, bi, start_b))
                queue.append((start_a + match_length, aj, start_b + match_length, bj))

            matches.append(match)

        matches.sort()
        return matches

dialogue_conflict = False
def dialogue_conflict_handler(a_hunk, b_hunk, o_hunk):
    global dialogue_conflict
    dialogue_conflict = True

    yield DialogueLine(CONFLICT_LINE.format(CONFLICT_MARKERS[args.conflict_marker]["ours"]))
    yield from a_hunk

    if args.diff3:
        yield DialogueLine(CONFLICT_LINE.format(CONFLICT_MARKERS[args.conflict_marker]["ancestor"]))
        yield from o_hunk

    yield DialogueLine(CONFLICT_LINE.format(CONFLICT_MARKERS[args.conflict_marker]["theirs"]))
    yield from b_hunk
    yield DialogueLine(CONFLICT_LINE.format(CONFLICT_MARKERS[args.conflict_marker]["end"]))

style_conflict = False
def style_conflict_handler(a_hunk, b_hunk, o_hunk):
    global style_conflict
    style_conflict = True

    for line in a_hunk:
        line.Name = "Own$" + line.Name
        yield line

    for line in b_hunk:
        line.Name = "Other$" + line.Name
        yield line

def diff3(A, O, B, conflict_handler, **kwargs):
    matches_OA = LineMatcher(O, A, **kwargs).find_matches()
    matches_OB = LineMatcher(O, B, **kwargs).find_matches()

    def map_indices(matches):
        ind_map = collections.OrderedDict()
        for (o_start, t_start, match_length) in matches:
            for i in range(match_length):
                ind_map[o_start + i] = t_start + i
        return ind_map

    def hunks_equal(list1, hunk1, list2, hunk2):
        return len(hunk1) == len(hunk2) and \
            all(list1[i] == list2[j] for i, j in zip(hunk1, hunk2))

    def process_hunks(a_hunk, b_hunk, o_hunk):
        a_changed = not hunks_equal(A, a_hunk, O, o_hunk)
        b_changed = not hunks_equal(B, b_hunk, O, o_hunk)
        ab_equal = hunks_equal(A, a_hunk, B, b_hunk)

        if ab_equal or (a_changed and not b_changed):
            for i in a_hunk:
                yield A[i]
        elif b_changed and not a_changed:
            for i in b_hunk:
                yield B[i]
        else:
            yield from conflict_handler((A[i] for i in a_hunk),
                                        (B[i] for i in b_hunk),
                                        (O[i] for i in o_hunk))

    o_to_a = map_indices(matches_OA)
    o_to_b = map_indices(matches_OB)

    prev_a = prev_b = prev_o = -1
    # dict is sorted by index
    for o in o_to_a:
        if o not in o_to_b:
            continue

        a = o_to_a[o]
        b = o_to_b[o]

        line = O[o].merge(A[a], O[o], B[b])
        if line is None:
            continue

        if a > prev_a + 1 or b > prev_b + 1:
            yield from process_hunks(range(prev_a + 1, a),
                                     range(prev_b + 1, b),
                                     range(prev_o + 1, o))

        yield line

        prev_a = a
        prev_b = b
        prev_o = o

    yield from process_hunks(range(prev_a + 1, len(A)),
                             range(prev_b + 1, len(B)),
                             range(prev_o + 1, len(O)))


def main():
    global style_conflict

    mine = parse_file(args.myfile, 'Own')
    parent = parse_file(args.oldfile, 'Parent')
    theirs = parse_file(args.yourfile, 'Other')

    script_info = merge_keyval(mine["Script Info"],
                               parent["Script Info"],
                               theirs["Script Info"])

    project_garbage = merge_keyval(mine["Aegisub Project Garbage"],
                                   parent["Aegisub Project Garbage"],
                                   theirs["Aegisub Project Garbage"])

    extradata = merge_extradata(mine, parent, theirs)

    styles = list(diff3(
        mine["V4+ Styles"], parent["V4+ Styles"], theirs["V4+ Styles"],
        style_conflict_handler, memoizers=(lambda line: line.Name,)))

    events = list(diff3(mine["Events"], parent["Events"], theirs["Events"],
                        dialogue_conflict_handler,
                        memoizers=(lambda line: line.Text,
                                   lambda line: (line.Start, line.End))))

    # sanity check: find duplicate style names and disambiguate
    seen_styles = {}
    for line in styles:
        if line.Name in seen_styles:
            seen_line = seen_styles[line.Name]
            seen_line.Name = seen_line.source_file + "$" + seen_line.Name
            line.Name = line.source_file + "$" + line.Name
            style_conflict = True
        else:
            seen_styles[line.Name] = line

    if style_conflict:
        events.insert(0, DialogueLine(
            CONFLICT_LINE.format(
                "Style conflict detected. Please resolve the conflict "
                "through the style manager.")))

    used_extradata = {i for line in events for i in line.extra_indices}
    extradata = [line for line in extradata if line.Id in used_extradata]

    output = io.StringIO()

    output.write("[Script Info]\n")
    for line in script_info:
        output.write(str(line) + "\n")
    output.write("\n")

    if len(project_garbage) > 0:
        output.write("[Aegisub Project Garbage]\n")
        for line in project_garbage:
            output.write(str(line) + "\n")
        output.write("\n")

    output.write("[V4+ Styles]\n")
    output.write("Format: {}".format(", ".join(StyleLine.FIELDS)) + "\n")
    for line in styles:
        output.write(str(line) + "\n")
    output.write("\n")

    output.write("[Events]\n")
    output.write("Format: {}".format(", ".join(DialogueLine.FIELDS)) + "\n")
    for line in events:
        output.write(str(line) + "\n")

    if len(extradata) > 0:
        output.write("\n")
        output.write("[Aegisub Extradata]\n")
        for line in extradata:
            output.write(str(line) + "\n")

    if args.output is None:
        sys.stdout.buffer.write(output.getvalue().encode('utf-8-sig'))
    else:
        with open(args.output, 'w', encoding='utf-8-sig') as f:
            f.write(output.getvalue())

    if dialogue_conflict or style_conflict:
        sys.exit(1)

if __name__ == '__main__':
    main()
