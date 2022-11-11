from pathlib import Path

dumb_text_viewer = Path(__file__, "../../examples/dumb_text_viewer").resolve()
ubrotli = dumb_text_viewer.with_name("ubrotli")
bare_minimum = dumb_text_viewer.with_name("bare-minimum")
silly_name = Path(__file__, "../mock-packages/silly-name").resolve()
