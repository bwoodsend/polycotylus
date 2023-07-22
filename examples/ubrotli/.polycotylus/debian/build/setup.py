from setuptools import Extension, setup

setup(ext_modules=[
    Extension(name="ubrotli", sources=["wrapper.c"],
              extra_link_args=["-lbrotlienc", "-lbrotlidec"]),
])
