set -l distributions alpine arch debian fedora manjaro opensuse ubuntu void
set -l alpine_variants alpine:3.17 alpine:3.18 alpine:3.19 alpine:edge
set -l debian_variants debian:13
set -l fedora_variants fedora:37 fedora:38 fedora:39 fedora:40 fedora:41
set -l ubuntu_variants ubuntu:23.04 ubuntu:23.10
set -l void_variants void:musl void:glibc
set -l all_variants $distributions $alpine_variants $debian_variants $fedora_variants $ubuntu_variants $void_variants
set -l atomic_flags --completion --list-localizations --configure --presubmit-check

complete -c polycotylus -f
complete -x -c polycotylus -n "not __fish_seen_subcommand_from $all_variants $atomic_flags" -a "$distributions"

# The --architecture flag – if a Linux distribution is already selected, offer only architectures valid on that distribution.
complete -c polycotylus -x -l architecture -n "not __fish_seen_subcommand_from architecture $all_variants $atomic_flags" -a 'aarch64 amd64 arm64 armel armhf armv7 i386 mips64el ppc64el ppc64le riscv64 s390x x86 x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from alpine $alpine_variants" -a 'aarch64 armv7 ppc64le x86 x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from arch" -a 'x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from debian" -a 'amd64 arm64 armel armhf i386 mips64el ppc64el riscv64 s390x'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from fedora" -a 'x86_64 aarch64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from manjaro" -a 'x86_64 aarch64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from opensuse" -a 'x86_64 aarch64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from ubuntu" -a 'amd64 arm64 armhf ppc64el s390x'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from void $void_variants" -a 'aarch64 armv6l armv7l x86_64'

# Suggest variants of distributions only if the user has already started typing the distribution's name.
complete -x -c polycotylus -n 'not __fish_seen_subcommand_from $all_variants && string match -rq -- a (commandline -t)' -a "$alpine_variants"
complete -x -c polycotylus -n 'not __fish_seen_subcommand_from $all_variants && string match -rq -- d (commandline -t)' -a "$debian_variants"
complete -x -c polycotylus -n 'not __fish_seen_subcommand_from $all_variants && string match -rq -- f (commandline -t)' -a "$fedora_variants"
complete -x -c polycotylus -n 'not __fish_seen_subcommand_from $all_variants && string match -rq -- u (commandline -t)' -a "$ubuntu_variants"
complete -x -c polycotylus -n 'not __fish_seen_subcommand_from $all_variants && string match -rq -- v (commandline -t)' -a "$void_variants"

# Suggest GPG signing only for distributions that use it or when no distribution is given.
complete -c polycotylus -x -l gpg-signing-id -n "not __fish_seen_subcommand_from $all_variants || __fish_seen_subcommand_from arch fedora $fedora_variants manjaro opensuse" -a '(type -q gpg && __fish_complete_gpg_key_id gpg --list-secret-keys)'
# Likewise with VoidLinux signing certificates.
complete -c polycotylus -r -l void-signing-certificate -n "not __fish_seen_subcommand_from $all_variants || __fish_seen_subcommand_from void $void_variants"

complete -c polycotylus -f -s q -l quiet -d 'Decrease verbosity'
complete -c polycotylus -f -l post-mortem -d 'Enter container on error'
complete -c polycotylus -f -s h -l help -d 'Show help'

complete -c polycotylus -x -l completion -n "not __fish_seen_subcommand_from $all_variants" -a 'fish' -d 'Generate shell completions'
complete -c polycotylus -x -l list-localizations -n "not __fish_seen_subcommand_from $all_variants" -a 'language region modifier'
complete -c polycotylus -l configure -n "not __fish_seen_subcommand_from $all_variants" -d 'List/get/set/clear global settings'
complete -c polycotylus -l presubmit-check -n "not __fish_seen_subcommand_from $all_variants" -d 'Perform official package repositories specific checks'
