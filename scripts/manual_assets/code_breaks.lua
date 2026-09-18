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

local function breakable_code(code)
  local out = {}
  for ch in code.text:gmatch(".") do
    out[#out + 1] = LATEX_ESC[ch] or ch
    if BREAK_AFTER[ch] then out[#out + 1] = "\\allowbreak{}" end
  end
  return pandoc.RawInline("latex", "\\texttt{" .. table.concat(out) .. "}")
end

return {
  {
    traverse = "topdown",
    Header = function(h)
      return h, false -- keep Code inlines intact inside headings (PDF bookmarks)
    end,
    Code = breakable_code,
  },
}
