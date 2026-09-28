import sys
sys.path.insert(0, "site-packages")
import defcon

def make_ufo(path, glyphs, weight=400):
    font = defcon.Font()
    font.info.familyName = "RuleTest"
    font.info.styleName = f"Weight{weight}"
    font.info.unitsPerEm = 1000
    font.info.ascender = 800
    font.info.descender = -200
    for name in glyphs:
        g = font.newGlyph(name)
        g.width = 500
        pen = g.getPen()
        pen.moveTo((0,0))
        pen.lineTo((0,500))
        pen.lineTo((500,500))
        pen.lineTo((500,0))
        pen.closePath()
    font.save(path)

# base master: has 'dollar' and 'cent' but NOT 'dollar.rvrn' or 'cent.rvrn'
make_ufo("sources/Regular.ufo", ["dollar", "cent", "a", "b"], weight=400)
# heavy master (non-sparse), also lacks .rvrn glyphs
make_ufo("sources/Bold.ufo", ["dollar", "cent", "a", "b"], weight=700)
# sparse correction master carrying the .rvrn glyphs only
make_ufo("sources/Bold-sparse.ufo", ["dollar", "dollar.rvrn", "cent.rvrn"], weight=700)
print("done")
