--[[
code_breaks.lua — let long inline code wrap at its separators, document-wide.

LaTeX's \texttt cannot break inside a word, so a long dotted parameter path or a
src/...::test_name citation in prose runs past the right margin and clips
(owner-flagged on the first render review, 2026-09-17 — the tables had the same
defect and got this treatment first; this filter generalizes it). Every Code
inline becomes raw LaTeX with a break opportunity after each separator
(. _ / : -), LaTeX-escaped.

Headers are skipped (topdown traversal, no descent): a RawInline in a heading
would fall out of the hyperref PDF bookmark text.

Must run AFTER wide_tables.lua: that filter measures column content with
pandoc.utils.stringify, which sees RawInline as empty.
]]

local LATEX_ESC = {
  ["\\"] = "\\textbackslash{}", ["{"] = "\\{", ["}"] = "\\}", ["$"] = "\\$",
  ["&"] = "\\&", ["#"] = "\\#", ["^"] = "\\textasciicircum{}", ["_"] = "\\_",
  ["%"] = "\\%", ["~"] = "\\textasciitilde{}",
}

local BREAK_AFTER = { ["."] = true, ["_"] = true, ["/"] = true, [":"] = true, ["-"] = true }

local function with_breaks(text)
  local out = {}
  for ch in text:gmatch(".") do
    out[#out + 1] = LATEX_ESC[ch] or ch
    if BREAK_AFTER[ch] then out[#out + 1] = "\\allowbreak{}" end
  end
  return table.concat(out)
end

local function breakable_code(code)
  return pandoc.RawInline("latex", "\\texttt{" .. with_breaks(code.text) .. "}")
end

-- A generated cell often names an identifier in plain prose rather than in a code
-- span (`radiant.api.shipped_atmosphere_families()` in an atmosphere parameter's
-- description). LaTeX then hyphenates it like an ordinary word — "radi-ant.api" —
-- or overflows the cell (CU-370 III-007). Give such a token the same separator
-- break opportunities the code spans get; the inserted penalties also stop TeX
-- hyphenating across them, so identifiers break at `.`/`_`/`/`, never mid-word.
local LONG_TOKEN_MIN = 20

local function breakable_token(str)
  if #str.text < LONG_TOKEN_MIN then return nil end
  if not str.text:find("[._/]") then return nil end
  return pandoc.RawInline("latex", with_breaks(str.text))
end

return {
  {
    traverse = "topdown",
    Header = function(h)
      return h, false -- keep Code inlines intact inside headings (PDF bookmarks)
    end,
    Code = breakable_code,
  },
  -- Second pass, tables only: the Code inlines above are already RawInline, so
  -- this sees exactly the bare-prose identifiers.
  {
    Table = function(tbl)
      return pandoc.walk_block(tbl, { Str = breakable_token })
    end,
  },
}
