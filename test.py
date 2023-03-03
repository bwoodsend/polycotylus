import re
import json
import subprocess

import polycotylus

not_found = []
for i in json.load(open("/home/brenainn/Downloads/pypi-most-packages.json"))[:1000]:
    name = i["project"]
    try:
        polycotylus.Alpine.python_package(name)
    except:
        not_found.append(name)

script = "apk update\n"
script += "".join(f"echo {i} $(apk search -q " + max(re.findall("[a-z0-9A-Z]+", i), key=len) + ")\n" for i in not_found)
print(script)
subprocess.run(["docker", "run", "-i", "alpine", "ash"], text=True, input=script).stdout
