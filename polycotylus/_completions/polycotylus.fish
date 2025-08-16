set -l distributions alpine arch debian fedora manjaro ubuntu void
set -l alpine_tags alpine:3.17 alpine:3.18 alpine:3.19 alpine:3.20 alpine:3.21 alpine:3.22 alpine:edge
set -l debian_tags debian:13 debian:14
set -l fedora_tags fedora:37 fedora:38 fedora:39 fedora:40 fedora:41 fedora:42 fedora:43 fedora:44
set -l ubuntu_tags ubuntu:24.04 ubuntu:24.10 ubuntu:25.04 ubuntu:25.10
set -l void_tags void:musl void:glibc
set -l all_tags $distributions $alpine_tags $debian_tags $fedora_tags $ubuntu_tags $void_tags
set -l atomic_flags --completion --list-localizations --configure --presubmit-check

complete -c polycotylus -f
complete -x -c polycotylus -n "not __fish_seen_subcommand_from $all_tags $atomic_flags" -a "$distributions"

# The --architecture flag – if a Linux distribution is already selected, offer only architectures valid on that distribution.
complete -c polycotylus -x -l architecture -n "not __fish_seen_subcommand_from architecture $all_tags $atomic_flags" -a 'aarch64 amd64 arm64 armel armhf armv7 i386 mips64el ppc64el ppc64le riscv64 s390x x86 x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from $alpine_tags[1..3]" -a 'aarch64 armv7 ppc64le x86 x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from alpine $alpine_tags[4..]" -a 'aarch64 armv7 ppc64le riscv64 x86 x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from arch" -a 'x86_64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from debian $debian_tags" -a 'amd64 arm64 armel armhf i386 mips64el ppc64el riscv64 s390x'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from fedora $fedora_tags" -a 'x86_64 aarch64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from manjaro" -a 'x86_64 aarch64'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from ubuntu $ubuntu_tags" -a 'amd64 arm64 armhf ppc64el s390x'
complete -c polycotylus -x -l architecture -n "__fish_seen_subcommand_from void $void_tags" -a 'aarch64 armv6l armv7l x86_64'

# Suggest a distribution's tags only if the user has already started typing the distribution's name.
complete -x -c polycotylus -n 'not __fish_seen_subcommand_from $all_tags && string match -rq -- a (commandline -t)' -a "$alpine_tags"
complete -x -c polycotylus -n 'not __fish_seen_subcommand_from $all_tags && string match -rq -- d (commandline -t)' -a "$debian_tags"
complete -x -c polycotylus -n 'not __fish_seen_subcommand_from $all_tags && string match -rq -- f (commandline -t)' -a "$fedora_tags"
complete -x -c polycotylus -n 'not __fish_seen_subcommand_from $all_tags && string match -rq -- u (commandline -t)' -a "$ubuntu_tags"
complete -x -c polycotylus -n 'not __fish_seen_subcommand_from $all_tags && string match -rq -- v (commandline -t)' -a "$void_tags"

# Suggest GPG signing only for distributions that use it or when no distribution is given.
complete -c polycotylus -x -l gpg-signing-id -n "not __fish_seen_subcommand_from $all_tags || __fish_seen_subcommand_from arch fedora $fedora_tags manjaro" -a '(type -q gpg && __fish_complete_gpg_key_id gpg --list-secret-keys)'
# Likewise with VoidLinux signing certificates.
complete -c polycotylus -r -l void-signing-certificate -n "not __fish_seen_subcommand_from $all_tags || __fish_seen_subcommand_from void $void_tags"

complete -c polycotylus -f -s q -l quiet -d 'Decrease verbosity'
complete -c polycotylus -f -l post-mortem -d 'Enter container on error'
complete -c polycotylus -f -s h -l help -d 'Show help'

complete -c polycotylus -x -l completion -n "not __fish_seen_subcommand_from $all_tags" -a 'fish' -d 'Generate shell completions'
complete -c polycotylus -x -l list-localizations -n "not __fish_seen_subcommand_from $all_tags" -a 'language region modifier'
complete -c polycotylus -l configure -n "not __fish_seen_subcommand_from $all_tags" -d 'List/get/set/clear global settings'
complete -c polycotylus -l presubmit-check -n "not __fish_seen_subcommand_from $all_tags" -d 'Perform official package repositories specific checks'
