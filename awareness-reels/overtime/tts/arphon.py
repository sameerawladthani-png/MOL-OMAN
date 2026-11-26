FATHA, KASRA, DAMMA, SUKUN, SHADDA = 'َ', 'ِ', 'ُ', 'ْ', 'ّ'
TAN_F, TAN_K, TAN_D = 'ً', 'ٍ', 'ٌ'
VOW = {FATHA: 'a', KASRA: 'i', DAMMA: 'u'}
CONS = {'ب':'b','ت':'t','ث':'θ','ج':'dʒ','ح':'ħ','خ':'χ','د':'d','ذ':'ð','ر':'r','ز':'z','س':'s','ش':'ʃ','ص':'s̪','ض':'dˤ','ط':'t̪','ظ':'ðˤ','ع':'ʕ','غ':'ɣ','ف':'f','ق':'q','ك':'k','ل':'l','م':'m','ن':'n','ه':'h','و':'w','ي':'j','ء':'ʔ','أ':'ʔ','إ':'ʔ','ؤ':'ʔ','ئ':'ʔ','ة':'t'}
EMPH = set('صضطظ'); SUN = set('تثدذرزسشصضطظلن')

def letters(word):
    out = []
    for ch in word:
        if 'ً' <= ch <= 'ْ':
            if out: out[-1][1].append(ch)
        else: out.append([ch, []])
    return out

def word_segments(word, phrase_initial, prev_ends_vowel, pausal):
    L = letters(word); segs = []; i = 0
    if L and L[0][0] == 'ا' and not L[0][1]:   # همزة وصل
        nxt = L[1][0] if len(L) > 1 else ''
        is_al = nxt == 'ل' and len(L) > 2 and (SUKUN in L[1][1] or not L[1][1])
        if phrase_initial: segs += [('C','ʔ',False), ('V','a' if is_al else 'i',False)]
        elif not prev_ends_vowel: segs += [('V','i',False)]
        i = 1
        if is_al:
            sun = L[2][0] in SUN
            if not sun: segs.append(('C','l',False))
            i = 2
            if sun and SHADDA not in L[2][1]: L[2][1].append(SHADDA)
    while i < len(L):
        ch, mk = L[i]
        if ch == 'ا' and i > 0 and i+1 < len(L) and L[i+1][0] == 'ل' and not any(m in VOW for m in L[i+1][1]) and not mk and L[i-1][1] and (i == 1 or (i == 2 and L[0][0] in 'وف')):
            nxt = L[i+2][0] if i+2 < len(L) else ''   # بِال / وَال
            if nxt in SUN:
                if SHADDA not in L[i+2][1]: L[i+2][1].append(SHADDA)
                i += 2; continue
            segs.append(('C','l',False)); i += 2; continue
        if ch in ('ا','ى'):
            if segs and segs[-1][0] == 'V' and segs[-1][1] == 'a': segs[-1] = ('V','a',True)
            i += 1; continue
        if ch == 'آ': segs += [('C','ʔ',False), ('V','a',True)]; i += 1; continue
        if ch in 'وي' and not any(m in mk for m in (FATHA,KASRA,DAMMA,SHADDA,TAN_F,TAN_K,TAN_D)) and segs and segs[-1][0] == 'V' and not segs[-1][2]:
            pv = segs[-1][1]
            if (ch == 'و' and pv == 'u') or (ch == 'ي' and pv == 'i'):
                segs[-1] = ('V', pv, True); i += 1; continue
        if ch == 'ة' and (pausal and i == len(L)-1 or SUKUN in mk): i += 1; continue
        if ch not in CONS: i += 1; continue
        c = CONS[ch]; emph = ch in EMPH
        segs.append(('C', c, emph))
        if SHADDA in mk: segs.append(('C', c, emph))
        for m in mk:
            if m in VOW: segs.append(('V', VOW[m], False))
            elif m == TAN_F: segs += [('V','a',False), ('C','n',False)]
            elif m == TAN_K: segs += [('V','i',False), ('C','n',False)]
            elif m == TAN_D: segs += [('V','u',False), ('C','n',False)]
        i += 1
    return segs

def render(segs):
    vidx = [k for k, s in enumerate(segs) if s[0] == 'V']
    if not vidx: return ''.join(s[1] for s in segs)
    syl = []
    for n, k in enumerate(vidx):
        nxt = vidx[n+1] if n+1 < len(vidx) else len(segs)
        coda = [j for j in range(k+1, nxt) if segs[j][0] == 'C']
        ncoda = len(coda) - (1 if n+1 < len(vidx) and coda else 0)
        syl.append((k, segs[k][2] or ncoda >= 1, (segs[k][2] and ncoda >= 1) or ncoda >= 2))
    N = len(syl)
    st = 0 if N == 1 else N-1 if syl[-1][2] else N-2 if syl[-2][1] else N-3 if N >= 3 else 0
    out = ''; prev_c = None
    for k, s in enumerate(segs):
        if s[0] == 'C':
            out += 'ː' if (prev_c == s[1] and segs[k-1][0] == 'C') else s[1]; prev_c = s[1]
        else:
            emph = k > 0 and segs[k-1][0] == 'C' and segs[k-1][2]
            out += ('ˈ' if k == syl[st][0] else '') + s[1] + ('.' if emph else '') + ('ː' if s[2] else ''); prev_c = None
    return out

def phonemize(text):
    import re
    toks = re.findall(r'[ء-ْ]+|[.,،؟?!]', text)
    out = []; phrase_init = True; prev_v = False
    for n, t in enumerate(toks):
        if t in '.,،؟?!':
            out.append({'،': ',', '؟': '?'}.get(t, t)); phrase_init = True; continue
        pausal = n+1 >= len(toks) or toks[n+1] in '.,،؟?!'
        segs = word_segments(t, phrase_init, prev_v, pausal)
        out.append(render(segs)); prev_v = bool(segs) and segs[-1][0] == 'V'; phrase_init = False
    s = ''
    for o in out: s = (s.rstrip() + o + ' ') if o in ',.?!' else (s + o + ' ')
    return s.strip()
