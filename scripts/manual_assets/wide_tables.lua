--[[
wide_tables.lua — give overlong GFM tables proportional column widths.

The `gfm` reader parses pipe tables without pandoc's column-width heuristic (the
`markdown` reader applies it when a table's source line exceeds --columns), so every
wide table lands in LaTeX as plain `l` columns whose long cells overflow the right
margin and clip — first seen on the Parameter Reference and Error Taxonomy chapters
of the first real PDF build (2026-09-17). This filter replicates the heuristic at
the AST level, reader-independent:

  * tables whose natural one-line width fits the text line keep their default
    (auto) column sizing — short tables stay compact;
  * wider tables get relative p{} widths proportional to each column's longest
    cell, with a floor so narrow columns (Type, Unit) stay readable.

Pure width assignment: no content is touched, and tables that already carry
explicit widths (from a future reader or filter) are left alone.
]]

-- Longest rendered line, in characters, of the blocks in one table cell.
local function cell_width(cell)
  local text = pandoc.utils.stringify(pandoc.Pandoc(cell.contents))
  local widest = 0
  for line in (text .. "\n"):gmatch("([^\n]*)\n") do
    if #line > widest then widest = #line end
  end
  return widest
end

-- Characters that fit one body line of the manuals (letterpaper, 1in margins,
-- \footnotesize longtable per manual_header.tex). Beyond this, wrap.
local FIT_CHARS = 100
-- No column drops below this fraction of the line, however short its content.
local MIN_FRAC = 0.06
-- A column's contribution to the proportional split is capped: without the cap a
-- prose Description column hundreds of characters wide starves every other column,
-- and an unbreakable monospace dot-path then overprints its neighbours (seen on
-- the Parameter Reference's first wrapped render). Prose wraps; code does not —
-- so the cap protects the code columns' share.
local CAP_CHARS = 46

local function widen(tbl)
  local ncols = #tbl.colspecs
  if ncols < 2 then return nil end
  for _, spec in ipairs(tbl.colspecs) do
    if spec[2] ~= nil then return nil end -- explicit widths present: hands off
  end

  local widths = {}
  for i = 1, ncols do widths[i] = 1 end -- floor of one character per column

  local function scan(rows)
    for _, row in ipairs(rows) do
      for i, cell in ipairs(row.cells) do
        local w = cell_width(cell)
        if i <= ncols and w > widths[i] then widths[i] = w end
      end
    end
  end
  scan(tbl.head.rows)
  for _, body in ipairs(tbl.bodies) do
    scan(body.head)
    scan(body.body)
  end
  scan(tbl.foot.rows)

  local total = 0
  for i = 1, ncols do total = total + widths[i] end
  if total <= FIT_CHARS then return nil end -- fits as-is: keep auto sizing

  -- Proportional fractions from CAPPED widths, with a floor, renormalized to 1.
  local capped_total = 0
  for i = 1, ncols do capped_total = capped_total + math.min(widths[i], CAP_CHARS) end
  local fracs, sum = {}, 0
  for i = 1, ncols do
    fracs[i] = math.max(math.min(widths[i], CAP_CHARS) / capped_total, MIN_FRAC)
    sum = sum + fracs[i]
  end
  for i = 1, ncols do
    tbl.colspecs[i] = { tbl.colspecs[i][1], fracs[i] / sum }
  end
  -- Cell code spans wrap via code_breaks.lua, which runs after this filter.
  return tbl
end

return { { Table = widen } }
