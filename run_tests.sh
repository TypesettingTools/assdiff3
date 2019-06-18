#!/bin/bash

STATUS=0
for i in tests/*; do
    echo -e "==== Running test $i ====\n"
    diff <(python assdiff3.py "$i/A.ass" "$i/O.ass" "$i/B.ass") "$i/result.ass"
    if [ $? -ne 0 ]; then
        STATUS=1
        echo -e "\n!!!! TEST FAILED !!!!\n"
    fi
done

exit $STATUS
