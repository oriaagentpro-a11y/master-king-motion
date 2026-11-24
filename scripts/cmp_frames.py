"""Comparaison réf. | film au même instant, sur une zone : python tools/cmp_frames.py out.png ref.mp4 crop=x0,y0,x1,y1 f:T [f:T ...]
(f = image réf., T = temps du film déjà capturé dans out/snap/tT.png ; zone en pixels film 1080x1920)."""
import sys, cv2, numpy as np
out, ref, crop = sys.argv[1], sys.argv[2], list(map(int, sys.argv[3].split('=')[1].split(',')))
x0, y0, x1, y1 = crop; cap = cv2.VideoCapture(ref); rows = []
for ft in sys.argv[4:]:
    f, T = ft.split(':'); cap.set(cv2.CAP_PROP_POS_FRAMES, int(f)); ok, r = cap.read(); r = cv2.resize(r, (1080, 1920))
    o = cv2.imread(f'out/snap/t{float(T):.2f}.png'); a, b = r[y0:y1, x0:x1], o[y0:y1, x0:x1]
    cv2.putText(a, f'REF f{f}', (8, 28), 0, 0.9, (255, 0, 255), 2); cv2.putText(b, f'MONNIZ {float(T):.2f}s', (8, 28), 0, 0.9, (255, 0, 255), 2)
    rows.append(np.hstack([a, np.full((a.shape[0], 10, 3), 200, np.uint8), b]))
cv2.imwrite(out, cv2.resize(np.vstack(rows), None, fx=0.6, fy=0.6))
