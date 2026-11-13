# Application icon

Place the original robot artwork at `app-icon.png` in this directory. The
startup code loads this PNG unchanged as the Tk application icon and sets the
running macOS Dock icon through AppKit. The image object stays alive for the
window's lifetime.

The image displayed in the icon request was not exposed as a downloadable file
to the cloud workspace. The original asset still needs to be supplied; no
substitute artwork is bundled.

This configures the running app's icon. A Finder icon for a packaged `.app`
requires a bundle and `.icns` resource; the existing `.command` remains a launcher.
The macOS AppKit path requires native Mac verification.
