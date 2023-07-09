set -l distributions alpine arch fedora manjaro opensuse void
set -l void_variants void:musl void:glibc
set -l all_variants $distributions $void_variants

complete -c polycotylus -f
complete -x -c polycotylus -n "not __fish_seen_subcommand_from $all_variants" -a "$distributions"

# The --architecture flag – if a Linux distribution is already selected, offer only architectures valid on that distribution.
complete -c polycotylus -x -l architecture -n "not __fish_seen_subcommand_from architecture $all_variants" -a 'aarch64 armv7 ppc64le x86 x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from alpine" -a 'aarch64 armv7 ppc64le x86 x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from arch" -a 'x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from fedora" -a 'x86_64 aarch64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from manjaro" -a 'x86_64 aarch64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from opensuse" -a 'x86_64 aarch64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from void $void_variants" -a 'aarch64 armv6l armv7l x86_64'

# Suggest variants of distributions only if the user has already started typing the distribution's name.
complete -x -c polycotylus -n 'not __fish_seen_subcommand_from $all_variants && string match -rq -- v (commandline -t)' -a "$void_variants"

complete -c polycotylus -f -s q -l quiet -d 'Decrease verbosity'
complete -c polycotylus -f -l post-mortem -d 'Enter container on error'
complete -c polycotylus -f -s h -l help -d 'Show help'

complete -c polycotylus -x -l completion -n "not __fish_seen_subcommand_from $all_variants" -a 'fish' -d 'Generate shell completions'
complete -c polycotylus -x -l list-localizations -n "not __fish_seen_subcommand_from $all_variants" -a 'language region modifier'
