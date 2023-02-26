set -l distributions alpine arch fedora manjaro void
complete -x -c polycotylus -n "not __fish_seen_subcommand_from $distributions" -a "$distributions"

complete -c polycotylus -x -l architecture -n "not __fish_seen_subcommand_from architecture $distributions" -a 'aarch64 armv7 ppc64le s390x x86 x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from alpine" -a 'aarch64 armv7 ppc64le s390x x86 x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from arch" -a 'x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from fedora" -a 'x86_64 aarch64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from manjaro" -a 'x86_64 aarch64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from void" -a 'x86_64'

complete -c polycotylus -f -s q -l quiet -d 'Decrease verbosity'

complete -c polycotylus -x -l completion -a 'fish'
complete -c polycotylus -x -l list-localizations -a 'language region modifier'
