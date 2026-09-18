--[[
internal_anchors.lua — drop the repo's implementation-anchor paragraphs from the
typeset manuals.

The theory chapters double as the repository's physics-assurance layer: every
equation carries a "**In RADIANT.** <module>::<function> · anchored by <test>"
paragraph (and the atmosphere chapter the sibling "*Record:* <CU> — *Enforced
by:* <test>" convention). In the repo those anchors are load-bearing — they are
how a maintainer or agent checks that a doc claim is enforced before trusting
it. To a manual reader they are unclickable monospace noise (owner-ruled
2026-09-17). The sources keep their anchors; this filter drops the paragraphs at
build time, and the Introduction's "how to read this manual" section states
once that every claim is anchored in the repository sources.

A paragraph is dropped when its FIRST inline is the convention marker:
  * Strong text  "In RADIANT."  (the pointer paragraph)
  * Strong text  "Citation convention."  (the paragraph explaining the
    Record/Enforced convention, meaningless once its instances are gone)
  * Emph text    "Record:"  or  "Enforced by:"  (the atmosphere convention;
    Record and Enforced usually share one paragraph, sometimes split)
Nothing else is touched: physics paragraphs never open with these markers.
]]

local STRONG_MARKERS = { ["In RADIANT."] = true, ["Citation convention."] = true }
local EMPH_MARKERS = { ["Record:"] = true, ["Enforced by:"] = true }

local function drop_anchor_para(para)
  local first = para.content[1]
  if first == nil then return nil end
  if first.t == "Strong" and STRONG_MARKERS[pandoc.utils.stringify(first)] then
    return {}
  end
  if first.t == "Emph" and EMPH_MARKERS[pandoc.utils.stringify(first)] then
    return {}
  end
  return nil
end

return { { Para = drop_anchor_para } }
