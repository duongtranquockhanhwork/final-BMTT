import fitz, json, sys
pdf, keys = sys.argv[1], json.load(open(sys.argv[2]))
doc = fitz.open(pdf)
pages = []
for pg in doc:
    L = [l.strip() for l in pg.get_text().split('\n') if l.strip()]
    pages.append((L[-1], L, '\t' in pg.get_text()))
toc_start = next(i for i, (_, L, _) in enumerate(pages) if L and L[0].startswith('TABLE OF CONTENTS'))
out = {}
def find(prefix, start, key, allow_tab=False):
    for i in range(start, len(pages)):
        lab, L, has_tab = pages[i]
        for l in L:
            if l.startswith(prefix[:30]) and (allow_tab or '\t' not in l):
                out[key] = lab; return i
    print('NOT FOUND', key); return start
pos = toc_start + 1
for t in keys['toc']:
    # skip TOC pages themselves: TOC lines have a tab
    pos = find(t, pos, t)
for f in keys['figs'] + keys['tabs']:
    find(f, toc_start + 1, f.lower().replace('figure', 'fig').replace('table', 'tab').rstrip('.'))
json.dump(out, open(sys.argv[3], 'w'), indent=1); print(out)
