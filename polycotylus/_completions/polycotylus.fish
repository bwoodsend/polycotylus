set -l distributions alpine arch fedora manjaro void
complete -x -c polycotylus -n "not __fish_seen_subcommand_from $distributions" -a "$distributions"

complete -c polycotylus -f -s q -l quiet -d 'Decrease verbosity'

complete -c polycotylus -x -l completion -a 'fish'
