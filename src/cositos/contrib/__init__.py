"""Optional, Python-only conveniences that sit *outside* the fixture-certified core.

Everything under :mod:`cositos.contrib` may depend on the wider Python widget ecosystem
(notably ``ipywidgets``). None of it is imported by :mod:`cositos` itself, so the pure,
cross-language-portable core stays free of those dependencies. Import from here explicitly:

    from cositos.contrib import harvest, harvest_html
"""

from cositos.contrib.controls import dropdown, hbox, int_slider, vbox
from cositos.contrib.harvest import harvest, harvest_html

__all__ = ["harvest", "harvest_html", "int_slider", "dropdown", "vbox", "hbox"]
