--[[
heading_numbers.lua — strip literal ordinal prefixes from headings at build time.

The bound chapters carry hand-numbered headings ("## 3. Foundations") because the
repo's Markdown renders flat (mkdocs, GitHub) with no auto-numbering, and prose
cross-references ("see §3") lean on those literals. The manuals build with
--number-sections, so the same headings typeset doubled: "4.3 3. Foundations"
(owner-flagged on the first render review, 2026-09-17). Sources keep their
numbers; this filter drops the literal at build time only.

Only a leading ordinal WITH a trailing dot is stripped ("1.", "10.", "2.4.").
Scenario identifiers ("### 1.2 — VNIR Pan Imager") carry no trailing dot and are
meaningful names, not enumeration — they pass through untouched.
]]

local function strip_ordinal(header)
  local inlines = header.content
  local first = inlines[1]
  if first and first.t == "Str" and first.text:match("^%d+[%.%d]*%.$") then
    local second = inlines[2]
    if second and second.t == "Space" then
      local rest = pandoc.List(inlines)
      rest:remove(1)
      rest:remove(1)
      header.content = rest
      return header
    end
  end
  return nil
end

return { { Header = strip_ordinal } }
