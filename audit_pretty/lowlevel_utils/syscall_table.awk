BEGIN {
    print "# AUTOGENERATED. DO NOT EDIT BY HAND."
    print "def init(syscall_table):"
    print "    syscall_table['" ARCH "'] = {"
}
END {
    print "    }\n"
}
{
    print "        " $1 ": '"$2"',"
}