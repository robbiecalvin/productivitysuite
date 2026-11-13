import os
import pytest
from suite.app_icon import apply_app_icon


def test_missing_icon_keeps_startup_available(tmp_path):
    # Missing optional artwork must not try to initialize Tk or block launch.
    assert apply_app_icon(None, tmp_path / 'missing.png') is False


@pytest.mark.desktop
@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='Tk display required')
def test_png_loads_and_survives_python_garbage_collection(tmp_path):
    import gc
    import tkinter as tk
    root = tk.Tk()
    try:
        fixture = tk.PhotoImage(master=root, width=2, height=2)
        fixture.put('#123456', to=(0, 0, 2, 2))
        path = tmp_path / 'fixture.png'
        fixture.write(str(path), format='png')
        assert apply_app_icon(root, path)
        gc.collect()
        root.update()
        name = str(root._suite_app_icon)
        assert int(root.tk.call('image', 'width', name)) == 2
        assert root._suite_app_icon.get(0, 0) == (18, 52, 86)
    finally:
        root.destroy()
