set -l distributions alpine arch fedora manjaro opensuse void
complete -c polycotylus -f
complete -x -c polycotylus -n "not __fish_seen_subcommand_from $distributions" -a "$distributions"

complete -c polycotylus -x -l architecture -n "not __fish_seen_subcommand_from architecture $distributions" -a 'aarch64 armv7 ppc64le x86 x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from alpine" -a 'aarch64 armv7 ppc64le x86 x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from arch" -a 'x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from fedora" -a 'x86_64 aarch64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from manjaro" -a 'x86_64 aarch64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from opensuse" -a 'x86_64 aarch64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from void" -a 'aarch64 armv6l armv7l x86_64'

complete -c polycotylus -f -s q -l quiet -d 'Decrease verbosity'
complete -c polycotylus -f -l post-mortem -d 'Enter container on error'
complete -c polycotylus -f -s h -l help -d 'Show help'

complete -c polycotylus -x -l completion -n "not __fish_seen_subcommand_from $distributions" -a 'fish' -d 'Generate shell completions'
complete -c polycotylus -x -l list-localizations -n "not __fish_seen_subcommand_from $distributions" -a 'language region modifier'
