import re
from docker import from_env


class LazyImage:

    def __init__(self, base):
        self.base = base
        base = re.sub(r"\W+", "_", base)
        self.container_name = f"polycotylus_lazy_{base}"

    @property
    def container(self):
        docker = from_env()
        try:
            container = docker.containers.get(self.container_name)
        except:
            container = docker.containers.create(
                self.base, command="sh -c 'while true; do sleep 10; done'",
                name=self.container_name)
        if container.status != "running":
            container.start()
        return container

    def __call__(self, *args):
        return self.container.exec_run(*args)
