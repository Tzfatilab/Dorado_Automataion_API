"""Concise display labels; original filtration decisions remain source facts."""
import json
import re


LABELS = [
    (r'^(Edge filter:|Removed by the NanoTel edge filter:)', 'Read too short relative to running median'),
    (r'^Telomere density .+ below minimum ', 'Low telomere density'),
    (r'^Telomere start .+ exceeds maximum ', 'Telomere starts too late'),
    (r'^Read length .+ below minimum ', 'Total read too short'),
    (r'^Telomere density unavailable$', 'Density unavailable'),
    (r'^Edge-filter measurement unavailable$', 'Edge measurement unavailable'),
    (r'^Outside the displayed filtered population$', 'Reason unavailable'),
    (r'^specific filter reason unavailable\.?$', 'Reason unavailable'),
]
_COMPILED = [(re.compile(pattern, re.I), label) for pattern, label in LABELS]


def short_filter_reason(reason):
    """Shorten known reasons, keeping multiple failures and unknown text."""
    if not isinstance(reason, str):
        return reason
    parts = []
    for part in reason.split(';'):
        part = part.strip()
        label = next((label for pattern, label in _COMPILED if pattern.search(part)), part)
        if label and label not in parts:
            parts.append(label)
    return '; '.join(parts)


# Both workbook paths and legacy browser records use these same label rules.
FILTER_REASON_JAVASCRIPT = '''window.reportShortFilterReason = (() => {
  const rules = ''' + json.dumps(LABELS) + '''.map(([pattern,label])=>[new RegExp(pattern,'i'),label]);
  return reason => {
    if(typeof reason!=='string')return reason;
    const parts=reason.split(';').map(part=>{
      part=part.trim();return rules.find(([pattern])=>pattern.test(part))?.[1]??part;
    }).filter(Boolean);
    return [...new Set(parts)].join('; ');
  };
})();'''
