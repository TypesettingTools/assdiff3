git config --global merge.assdiff3.name "Three-way ASS merger"
git config --global merge.assdiff3.driver "'${PWD}/assdiff3.exe' --diff3 %A %O %B -o %A"
