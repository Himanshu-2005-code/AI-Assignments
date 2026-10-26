# The DSL: small grid -> grid functions (the "actions" of the search).
# Grids are 2D numpy int arrays; 0 is treated as the background colour.
# Hard-coded priors (Chollet's Core Knowledge): objects, symmetry/geometry, counting, colour.
import numpy as np

BG = 0


# Connected components of non-background cells (4-connected, any colour), as lists of (r, c).
def components(g, same_color=False):
    h, w = g.shape
    seen = np.zeros_like(g, dtype=bool)
    objs = []
    for r in range(h):
        for c in range(w):
            if g[r, c] == BG or seen[r, c]:
                continue
            stack, cells = [(r, c)], []
            seen[r, c] = True
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if (0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and g[ny, nx] != BG
                            and (not same_color or g[ny, nx] == g[r, c])):
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            objs.append(cells)
    return objs


# Crop the grid to the bounding box of the given cells.
def crop_cells(g, cells):
    ys, xs = zip(*cells)
    return g[min(ys):max(ys) + 1, min(xs):max(xs) + 1]


# Crop to the bounding box of all non-background cells.
def crop_content(g):
    cells = list(zip(*np.nonzero(g != BG)))
    return crop_cells(g, cells) if cells else g


# Crop to the largest object (most cells).
def crop_largest(g):
    objs = components(g)
    return crop_cells(g, max(objs, key=len)) if objs else g


# Crop to the smallest object.
def crop_smallest(g):
    objs = components(g)
    return crop_cells(g, min(objs, key=len)) if objs else g


# Keep only the largest object, erase the rest.
def keep_largest(g):
    objs = components(g)
    out = np.zeros_like(g)
    if objs:
        for y, x in max(objs, key=len):
            out[y, x] = g[y, x]
    return out


# Move every non-background cell as far as it can go in a direction (like gravity).
def gravity(g, direction):
    out = np.zeros_like(g)
    rot = {"down": 0, "up": 2, "left": 1, "right": 3}[direction]
    gg = np.rot90(g, rot)
    res = np.zeros_like(gg)
    for c in range(gg.shape[1]):
        col = [v for v in gg[:, c] if v != BG]
        if col:
            res[gg.shape[0] - len(col):, c] = col
    return np.rot90(res, -rot)


# Fill background cells that cannot reach the border (enclosed holes) with colour `color`.
def fill_enclosed(g, color):
    h, w = g.shape
    outside = np.zeros_like(g, dtype=bool)
    stack = [(r, c) for r in range(h) for c in (0, w - 1)] + [(r, c) for c in range(w) for r in (0, h - 1)]
    while stack:
        y, x = stack.pop()
        if 0 <= y < h and 0 <= x < w and not outside[y, x] and g[y, x] == BG:
            outside[y, x] = True
            stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    out = g.copy()
    out[(g == BG) & ~outside] = color
    return out


# Overlay: where g is background take the value from other.
def overlay(g, other):
    return np.where(g == BG, other, g)


# Colour that occurs most among non-background cells (BG if none).
def dominant_color(g):
    vals = g[g != BG]
    return int(np.bincount(vals).argmax()) if vals.size else BG


# Replace every colour a with colour b.
def recolor(g, a, b):
    return np.where(g == a, b, g)


# Paint every non-background cell with a single colour.
def paint_all(g, color):
    return np.where(g != BG, color, g)


# Map each colour to the other-colours-of-this-grid by frequency rank is too clever; keep simple ops only.
# Remove every cell of colour c.
def remove_color(g, c):
    return np.where(g == c, BG, g)


# The fixed (parameter-free) primitives: name -> function.
BASE = {
    "flip_h": lambda g: g[:, ::-1],
    "flip_v": lambda g: g[::-1, :],
    "rot90": lambda g: np.rot90(g, 1),
    "rot180": lambda g: np.rot90(g, 2),
    "rot270": lambda g: np.rot90(g, 3),
    "transpose": lambda g: g.T,
    "crop_content": crop_content,
    "crop_largest": crop_largest,
    "crop_smallest": crop_smallest,
    "keep_largest": keep_largest,
    "upscale2": lambda g: np.kron(g, np.ones((2, 2), dtype=g.dtype)),
    "upscale3": lambda g: np.kron(g, np.ones((3, 3), dtype=g.dtype)),
    "downscale2": lambda g: g[::2, ::2],
    "tile2x2": lambda g: np.tile(g, (2, 2)),
    "tile3x3": lambda g: np.tile(g, (3, 3)),
    "mirror_h": lambda g: np.hstack([g, g[:, ::-1]]),
    "mirror_v": lambda g: np.vstack([g, g[::-1, :]]),
    "mirror_both": lambda g: np.vstack([np.hstack([g, g[:, ::-1]]), np.hstack([g[::-1, :], g[::-1, ::-1]])]),
    "sym_h": lambda g: overlay(g, g[:, ::-1]),
    "sym_v": lambda g: overlay(g, g[::-1, :]),
    "sym_both": lambda g: overlay(overlay(g, g[:, ::-1]), overlay(g, g[:, ::-1])[::-1, :]),
    "left_half": lambda g: g[:, :g.shape[1] // 2],
    "right_half": lambda g: g[:, (g.shape[1] + 1) // 2:],
    "top_half": lambda g: g[:g.shape[0] // 2, :],
    "bottom_half": lambda g: g[(g.shape[0] + 1) // 2:, :],
    "fractal": lambda g: np.kron((g != BG).astype(g.dtype), g),
    "gravity_down": lambda g: gravity(g, "down"),
    "gravity_up": lambda g: gravity(g, "up"),
    "gravity_left": lambda g: gravity(g, "left"),
    "gravity_right": lambda g: gravity(g, "right"),
    "paint_dominant": lambda g: paint_all(g, dominant_color(g)),
}


# Build the full action list for one task: the base primitives plus colour-parameterised ones,
# where the colours are taken from the colours that actually appear in the demonstrations.
def build_actions(demos):
    colors = sorted({int(v) for i, o in demos for v in np.unique(np.concatenate([i.ravel(), o.ravel()]))})
    acts = dict(BASE)
    for a in colors:
        if a != BG:
            acts[f"remove_{a}"] = lambda g, a=a: remove_color(g, a)
            acts[f"fill_enclosed_{a}"] = lambda g, a=a: fill_enclosed(g, a)
            acts[f"paint_all_{a}"] = lambda g, a=a: paint_all(g, a)
        for b in colors:
            if a != b:
                acts[f"recolor_{a}_{b}"] = lambda g, a=a, b=b: recolor(g, a, b)
    return acts
