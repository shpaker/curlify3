"""Sphinx configuration for the curlify3 documentation."""

project = "curlify3"
author = "A.Shpak"
copyright = "A.Shpak"

extensions = [
    "myst_parser",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
]

# the pages are Markdown, like the README and the changelog they sit next to
source_suffix = {".md": "markdown"}
myst_enable_extensions = ["colon_fence", "deflist"]
# anchors for ## and ### headings, so pages can link to sections of each other
myst_heading_anchors = 3

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

html_theme = "furo"
html_title = "curlify3"
html_static_path: list[str] = []
html_theme_options = {
    "source_repository": "https://github.com/shpaker/curlify3/",
    "source_branch": "main",
    "source_directory": "docs/",
}

# the shell prompts and the output comments are not part of what gets copied
copybutton_prompt_text = r"\$ |>>> "
copybutton_prompt_is_regexp = True
