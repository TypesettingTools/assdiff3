
# Overview

```
usage: assdiff3.py [-h] [--output OUTPUT] myfile oldfile yourfile

Three-way merge of ASS files

positional arguments:
  myfile                The locally changed file
  oldfile               The parent file that both files diverged from
  yourfile              The remotely changed file

optional arguments:
  -h, --help            show this help message and exit
  --output OUTPUT, -o OUTPUT
                        File to output to
```

`assdiff3` performs a three-way merge of Advanced SubStation Alpha (ASS) files.
Unlike standard merging algorithms like `diff3`, `assdiff3` is a format-aware merger that ensures that **the output is always a valid ASS file**, and makes it possible to **merge non-conflicting changes to the same line**.
The main usecase for `assdiff3` is in conjunction with git, allowing for a more efficient workflow where e.g. timer and editor can work simultaneously on the same file, with few or no conflicts on merge.

# Caveats

`assdiff3` is based on the naive [diff3 algorithm](http://www.cis.upenn.edu/~bcpierce/papers/diff3-short.pdf), using the same greedy sequence matching algorithm as Python's [difflib.SequenceMatcher](https://docs.python.org/3/library/difflib.html#difflib.SequenceMatcher), and suffers from the same caveats, mainly:

* Identical lines inserted at different places in the file will not cause conflicts.
* Under certain rare conditions, the sequence matcher may produce suboptimal conflicting hunks: One single large conflicting hunk rather than several smaller hunks, each with the same number of unchanged lines separating them.

Additionally, `assdiff3` has a number of caveats of its own:

* `assdiff3` uses the start/end time and/or the text of a line to associate a changed line with a line from the original file.
If both timing and the text is changed, the changes cannot be merged with changes to the same line in another file.
* To avoid conflicts in the header sections, changes in the local file are always prioritized over changes in the remote file.
* To avoid conflicting extradata IDs, lines in the Aegisub Extradata section will be disambiguated to ensure that differing lines have different IDs across all three files.
This may cause seemingly random ID increments, but should not have any adverse effects.

# Installation on Windows

Clone or [download](https://github.com/TypesettingTools/assdiff3/archive/master.zip) the repository and run `configure_assdiff3_windows.sh` from the `dist` directory, either by right clicking and running with git bash, or by manually executing the script from e.g. git bash or WSL.
This will globally add the `assdiff3` merge driver to git.

Afterwards, create a `.gitattributes` file in your repository with the following contents:
```
*.ass merge=assdiff3
```

If you change the location of `assdiff3.exe`, you must rerun the configure script from the new directory.

# Installation on non-Windows

Install with pip (include the `--user` flag if you wish to install as user rather than root):
```
$ pip install git+https://github.com/TypesettingTools/assdiff3
```
This will add the `assdiff3` command to wherever pip installs binaries on your system (normally `~/.local/bin` on Linux if installing with `--user`).

Then configure the merge driver for git:
```
$ git config --global merge.assdiff3.name "Three-way ASS merger"
$ git config --global merge.assdiff3.driver "'$(which assdiff3)' %A %O %B -o %A"
```
Here we use the full path rather than simply `assdiff3` to ensure that the driver will work even if your git client of choice does not have `assdiff3` in its PATH.
If `assdiff3` is not in your path, either manually specify the full path to it, or use `python -m assdiff3 %A %O %B -o %A` as the driver command instead.

Finally, as on Windows, create a `.gitattributes` file in your repository containing
```
*.ass merge=assdiff3
```

# Example

Consider the following three files and the result of merging them (changes highlighted in **bold**):

<pre>
$ cat original.ass
[Script Info]
PlayResX: 1024
PlayResY: 576

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Gandhi Sans,40,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,1,1.92,0.8,2,120,120,32,1
Style: Default-alt,Gandhi Sans,40,&H00FFFFFF,&H000000FF,&H00481E14,&HA05A1613,-1,0,0,0,100,100,0,0,1,1.92,0.8,2,120,120,32,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:01:34.14,0:01:37.20,Default,,0,0,0,,line1
Dialogue: 0,0:01:37.20,0:01:38.85,Default,,0,0,0,,line2
Dialogue: 0,0:01:38.85,0:01:40.81,Default,,0,0,0,,line3
Dialogue: 0,0:01:40.81,0:01:42.84,Default,,0,0,0,,line4

$ cat local.ass
[Script Info]
PlayResX: <b>1920</b>
PlayResY: 576

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,<b>Arial</b>,40,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,1,1.92,0.8,2,120,120,32,1
Style: Default-alt,Gandhi Sans,<b>45</b>,&H00FFFFFF,&H000000FF,&H00481E14,&HA05A1613,-1,0,0,0,100,100,0,0,1,1.92,0.8,2,120,120,32,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:01:34.14,0:01:37.20,Default,,<b>10</b>,<b>10</b>,<b>10</b>,,<b>changed line1</b>
Dialogue: 0,0:01:37.20,0:01:38.85,Default,,0,0,0,,line2
Dialogue: 0,0:01:38.85,0:01:40.81,Default,,0,0,0,,<b>line3 changed locally</b>
Dialogue: 0,0:01:40.81,0:01:42.84,Default,,0,0,0,,line4

$ cat remote.ass
[Script Info]
PlayResX: <b>1280</b>
PlayResY: <b>1080</b>

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,<b>Helvetica</b>,40,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,1,1.92,0.8,2,120,120,32,1
Style: Default-alt,Gandhi Sans,40,&H00FFFFFF,&H000000FF,&H00481E14,&HA05A1613,<b>0</b>,0,0,0,100,100,0,0,1,1.92,0.8,2,120,120,32,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: <b>5</b>,<b>0:01:34.20,0:01:37.30</b>,Default,,0,0,0,,line1
Dialogue: 0,0:01:37.20,0:01:38.85,Default,,0,0,0,,line2
Dialogue: 0,0:01:38.85,0:01:40.81,Default,,0,0,0,,<b>line3 changed in remote</b>
Dialogue: 0,0:01:40.81,0:01:42.84,Default,,0,0,0,,line4

$ python assdiff3.py local.ass original.ass remote.ass
[Script Info]
PlayResX: <b>1920</b>
PlayResY: <b>1080</b>

[Aegisub Project Garbage]

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: <b>Own$Default</b>,<b>Arial</b>,40,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,1,1.92,0.8,2,120,120,32,1
Style: <b>Other$Default</b>,<b>Helvetica</b>,40,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,1,1.92,0.8,2,120,120,32,1
Style: Default-alt,Gandhi Sans,<b>45</b>,&H00FFFFFF,&H000000FF,&H00481E14,&HA05A1613,<b>0</b>,0,0,0,100,100,0,0,1,1.92,0.8,2,120,120,32,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
<b>Comment: 0,0:00:00.00,0:00:00.00,Default,,0,0,0,CONFLICT,Style conflict detected. Please resolve the conflict through the style manager.</b>
Dialogue: <b>5</b>,<b>0:01:34.20,0:01:37.30</b>,Default,,<b>10</b>,<b>10</b>,<b>10</b>,,<b>changed line1</b>
Dialogue: 0,0:01:37.20,0:01:38.85,Default,,0,0,0,,line2
<b>Comment: 0,0:00:00.00,0:00:00.00,Default,,0,0,0,CONFLICT,Start of own hunk</b>
Dialogue: 0,0:01:38.85,0:01:40.81,Default,,0,0,0,,<b>line3 changed locally</b>
<b>Comment: 0,0:00:00.00,0:00:00.00,Default,,0,0,0,CONFLICT,End of own hunk; Start of other hunk</b>
Dialogue: 0,0:01:38.85,0:01:40.81,Default,,0,0,0,,<b>line3 changed in remote</b>
<b>Comment: 0,0:00:00.00,0:00:00.00,Default,,0,0,0,CONFLICT,End of other hunk</b>
Dialogue: 0,0:01:40.81,0:01:42.84,Default,,0,0,0,,line4
</pre>
