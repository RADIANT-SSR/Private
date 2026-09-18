--[[
heading_numbers.lua — strip literal ordinal prefixes from headings at build time.

The bound chapters carry hand-numbered headings ("## 3. Foundations") because the
repo's Markdown renders flat (mkdocs, GitHub) with no auto-numbering, and prose
cross-references ("see §3") lean on those literals. The manuals build with
--number-sections, so the same headings typeset doubled: "4.3 3. Foundations"
(owner-flagged on the first render review, 2026-09-17). Sources keep their
numbers; this filter drops the literal at build time only.

Two ordinal shapes are stripped:
  * a trailing-dot ordinal — "1.", "10.", "2.4." ("## 3. Foundations");
  * a multi-part ordinal without the dot — "3.2", "2.10" ("### 3.2 Geometry
    interpolation"), UNLESS an em/en dash follows: scenario identifiers
    ("### 1.2 — VNIR Pan Imager") are names, not enumeration, and always
    carry the dash.
A bare single integer ("## 2026 Outlook") is never touched.
]]

local function strip_ordinal(header)
  local inlines = header.content
  local first = inlines[1]
  if not (first and first.t == "Str") then return nil end
  local second = inlines[2]
  if not (second and second.t == "Space") then return nil end

  local dotted = first.text:match("^%d+[%.%d]*%.$") ~= nil
  local multipart = first.text:match("^%d+%.%d+[%.%d]*$") ~= nil
  if multipart and not dotted then
    local third = inlines[3]
    if third and third.t == "Str" and (third.text == "—" or third.text == "–") then
      return nil -- scenario identifier, keep
    end
  end
  if dotted or multipart then
    local rest = pandoc.List(inlines)
    rest:remove(1)
    rest:remove(1)
    header.content = rest
    return header
  end
  return nil
end

return { { Header = strip_ordinal } }
