import json
import re
import itertools

with open("/home/brenainn/Downloads/distro-version-architecture-libc.json", "rb") as f:
    data = json.load(f)


def sluggify(name):
    name = name.lower().replace("gnu/", "").replace("os", "")
    name = re.sub("t?linux", "", name)
    return re.sub("[^a-z]+", "", name)


normalisations = {}
for item in data:
    name = sluggify(item["name"] or "")
    counts = normalisations.setdefault(name, {})
    counts[item["name"]] = counts.get(item["name"], 0) + int(item["counts"])
true_names = {name: max(counts, key=counts.get) for (name, counts) in normalisations.items()}

counts = {}
for item in data:
    name = true_names[sluggify(item["name"] or "")]
    variant = item["lib"] or "musl" if name == "Void" else item["version"]
    architecture = item["cpu"]
    if not (name and architecture and variant):
        continue
    by_architecture = counts.setdefault(name, {}).setdefault(variant, {})
    by_architecture[architecture] = by_architecture.get(architecture, 0) + int(item["counts"])


class Distribution:
    def __init__(self, name, distro_counts):
        self.name = name
        self.counts = distro_counts

    @property
    def variants(self):
        return sorted(self.counts, key=lambda x: [int(i) for i in re.findall(r"\d+", x)] or [1<<32, x])

    @property
    def _architecture_counts(self):
        return {x: sum(i.get(x, 0) for i in self.counts.values()) for x in itertools.chain(*self.counts.values())}

    @property
    def architectures(self):
        return sorted(self._architecture_counts, key=self._architecture_counts.get, reverse=True)

    @property
    def total(self):
        return sum(self._architecture_counts.values())


distributions = [Distribution(*i) for i in counts.items()]
distributions.sort(reverse=True, key=lambda x: x.total)
del distributions[100:]
del distributions[:20]

column_widths = {}
for distro in distributions:
    column_widths[0] = max(column_widths.get(0, 0), len(distro.name))
    for variant in distro.variants:
        column_widths[1] = max(column_widths.get(1, 0), len(variant))
        for (i, architecture) in enumerate(distro.architectures, 2):
            column_widths[i] = max((column_widths.get(i, 0), len(architecture), len(format(distro.counts[variant].get(architecture, 0), "3,"))))


def row(*items):
    out = ""
    for (i, item) in enumerate(items):
        out += "|" + item.ljust(column_widths[i])
    for i in range(i+1, len(column_widths)):
        out += " " * column_widths[i] + " "
    return out + "|"


def divider(x="-", y="-"):
    return "+".join(["", x * column_widths[0]] + [y * column_widths[i] for i in range(1, len(column_widths))] + [""])


print(divider("=", "="))
for distro in distributions:
    print(row(distro.name, "", *distro.architectures))
    print(divider(" "))
    for variant in distro.variants:
        print(row("", variant, *(format( distro.counts[variant].get(architecture, 0), "3,") for architecture in distro.architectures)))
        if variant != distro.variants[-1]:
            print(divider(" "))
    print(divider())
