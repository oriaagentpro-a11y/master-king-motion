"""Voix off hyper-réaliste générée par Claude lui-même (moteur VoxStudio Pro : API Gemini TTS de Google).

Usage :
  python3 scripts/voix_off.py --script lignes.txt --out voix/ [--voice Zephyr] [--profile tech_dynamic] [--style "…"]
  python3 scripts/voix_off.py --text "Une idée. Une phrase." --out voix/ --voice Puck
  python3 scripts/voix_off.py --check                 vérifie la clé et liste les modèles de voix disponibles
  python3 scripts/voix_off.py --set-key               à lancer PAR L'UTILISATEUR dans son terminal (saisie masquée)
lignes.txt : une ligne = une réplique = un fichier (l1.wav, l2.wav…). Une ligne peut commencer par « id | » pour
nommer le fichier, et contenir [pause 0.8s]. Sortie : un WAV 24 kHz mono par ligne + manifest.json (durées, texte,
voix, modèle). Claude cale ensuite chaque fichier sur son plan (audio_prep / calage) et vérifie par retranscription.

Clé API Google (Google AI Studio) — JAMAIS dans un dépôt, un dossier de projet ou un message affiché :
  1. variable d'environnement GEMINI_API_KEY (ou GEMINI_API_KEYS="clé1,clé2" pour la rotation), sinon
  2. fichier privé ~/.config/master-king-motion/gemini_api_key (une clé par ligne, droits 600).
Rotation automatique entre clés sur quota (429), clé invalide ou service saturé ; nouvel essai avec attente ;
repli automatique sur un autre modèle TTS si celui demandé n'existe plus.
Voix : Zephyr, Puck, Kore, Charon, Fenrir, Aoede, Leda, Orus, Callirrhoe, Iapetus… (voix Gemini prédéfinies).
Profils de style (VoxStudio) : studio_pro, documentary_deep, cinema_epic, luxury_intimate, tech_dynamic, storyteller_warm.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import os, sys, json, time, base64, wave, re, struct, getpass, urllib.request, urllib.error

API = 'https://generativelanguage.googleapis.com/v1beta'
KEY_FILE = os.path.join(os.path.expanduser('~'), '.config', 'master-king-motion', 'gemini_api_key')
MODELS = ['gemini-3.8-flash-tts', 'gemini-3.8-flash-lite-tts', 'gemini-3.1-flash-tts-preview', 'gemini-2.5-flash-preview-tts',
          'gemini-2.5-pro-preview-tts']
PROFILES = {   # repris de VoxStudio Pro (buildRealisticSpeechStyle)
    'studio_pro': "Studio broadcast acoustic master. Ultra-realistic French voice actor in an acoustically treated recording booth. Natural breathing cadence, subtle human micro-inflections, crisp consonants, warm proximity effect like a high-end Neumann U87 microphone, organic vocal cord vibration, absolutely zero robotic or flat synthesizer artifacts.",
    'documentary_deep': "Prestige documentary narration in French. Calibrated pacing, deep warm resonance, contemplative pauses, lifelike breathing, captivating and authentic human storytelling with intimate proximity.",
    'cinema_epic': "Cinematic trailer voiceover in French. Powerful emotional depth, controlled chest resonance, dramatic pauses, magnetic intensity and lifelike vocal timbre.",
    'luxury_intimate': "Luxury prestige fragrance and high-end brand French voice. Velvety, silky, whispering near-mic presence, delicate audible breath, intimate elegance and sophisticated diction.",
    'tech_dynamic': "Modern innovative startup and tech pitch in French. Authentic enthusiasm, communicative smile in the voice, sharp pacing, fluid natural liaisons, engaging and spontaneous.",
    'storyteller_warm': "Passionate and deeply empathetic French storyteller. Sensitive emotional modulations, natural phrasing, heartfelt human warmth and natural breathing intervals.",
}


def opt(k, d=None):
    a = sys.argv
    return a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else d


def keys():
    ks = [k.strip() for k in (os.environ.get('GEMINI_API_KEYS', '') + ',' + os.environ.get('GEMINI_API_KEY', '')).split(',') if k.strip()]
    if os.path.exists(KEY_FILE):
        ks += [l.strip() for l in open(KEY_FILE, encoding='utf-8') if l.strip() and not l.startswith('#')]
    return list(dict.fromkeys(ks))


def set_key():
    k = getpass.getpass('Collez votre clé API Google AI Studio (rien ne s\'affiche), puis Entrée : ').strip()
    if not k:
        sys.exit('aucune clé saisie')
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
    try:
        os.chmod(os.path.dirname(KEY_FILE), 0o700)
    except OSError:
        pass
    with open(KEY_FILE, 'a', encoding='utf-8') as f:
        f.write(k + '\n')
    try:
        os.chmod(KEY_FILE, 0o600)
    except OSError:
        pass
    print('Clé enregistrée dans', KEY_FILE)


def call(path, key, body=None, timeout=180):
    req = urllib.request.Request(f'{API}/{path}{"&" if "?" in path else "?"}key={key}',
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def err_text(e):
    try:
        return json.loads(e.read()).get('error', {}).get('message', str(e))
    except Exception:  # noqa: BLE001
        return str(e)


def available_models(ks):
    for k in ks:
        try:
            d = call('models?pageSize=200', k)
            return [m['name'].split('/', 1)[1] for m in d.get('models', []) if 'tts' in m['name'].lower()]
        except urllib.error.HTTPError as e:
            last = err_text(e)
        except urllib.error.URLError as e:
            sys.exit(f'Réseau : impossible de joindre l\'API Google ({e.reason}).')
    sys.exit(f'Aucune clé valide ({last}). Vérifiez la clé dans Google AI Studio.')


def tts(text, voice, style, model_list, ks, state):
    t = re.sub(r'\[pause\s*([0-1](?:\.\d+)?)s?\]', ' … ', text, flags=re.I)
    t = re.sub(r'\[pause\s*([2-9](?:\.\d+)?)s?\]', ' … … ', t, flags=re.I).strip()
    last = ''
    for model in model_list:
        for attempt in range(6):
            k = ks[state['rot'] % len(ks)]
            parts = [{'text': t, 'speechMetadata': {'style': style}}] if state.get('meta', True) else [{'text': f'{style}\n\nTexte à dire, mot pour mot : {t}'}]
            body = {'contents': [{'role': 'user', 'parts': parts}],
                    'generationConfig': {'responseModalities': ['AUDIO'],
                                         'speechConfig': {'voiceConfig': {'prebuiltVoiceConfig': {'voiceName': voice}}}}}
            try:
                d = call(f'models/{model}:generateContent', k, body)
                p = d['candidates'][0]['content']['parts'][0]['inlineData']
                return base64.b64decode(p['data']), p.get('mimeType', ''), model
            except urllib.error.HTTPError as e:
                last = f'{e.code} {err_text(e)}'
                if e.code == 400 and 'speechMetadata' in last and state.get('meta', True):
                    state['meta'] = False; continue          # API sans speechMetadata : style passé dans la consigne
                if e.code == 404:
                    break                                     # modèle retiré : modèle suivant
                if e.code in (429, 500, 503) or 'quota' in last.lower() or 'RESOURCE_EXHAUSTED' in last:
                    state['rot'] += 1; time.sleep(min(30, 2 + 3 * attempt)); continue
                if e.code in (401, 403):
                    state['rot'] += 1
                    if attempt >= len(ks):
                        sys.exit(f'Clé refusée par Google ({last}).')
                    continue
                sys.exit(f'Erreur Google ({last}).')
            except (KeyError, IndexError):
                last = 'réponse sans audio'; time.sleep(2)
            except urllib.error.URLError as e:
                last = str(e.reason); time.sleep(3)
    sys.exit(f'Échec de la génération : {last}')


def write_wav(path, data, mime):
    if data[:4] == b'RIFF':
        open(path, 'wb').write(data); return
    rate = int((re.search(r'rate=(\d+)', mime) or [None, 24000])[1])
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(data)


def main():
    if '--set-key' in sys.argv:
        return set_key()
    ks = keys()
    if not ks:
        sys.exit('NO_KEY : aucune clé API Google. Demander à l\'utilisateur de lancer lui-même dans son terminal :\n'
                 f'  python3 {os.path.abspath(__file__)} --set-key\n(ou de définir GEMINI_API_KEY). Ne jamais écrire la clé dans le projet.')
    have = available_models(ks)
    if '--check' in sys.argv:
        print(f'Clé(s) valide(s) : {len(ks)} · modèles de voix disponibles : {", ".join(have) or "aucun"}'); return
    want = [m for m in [opt('--model'), os.environ.get('GEMINI_TTS_MODEL')] + MODELS if m]
    model_list = [m for m in dict.fromkeys(want) if m in have] or have
    if not model_list:
        sys.exit('Aucun modèle de synthèse vocale disponible sur ce compte.')
    voice = opt('--voice', 'Zephyr'); prof = opt('--profile', 'tech_dynamic'); extra = opt('--style', '')
    style = PROFILES.get(prof, PROFILES['studio_pro']) + ' Diction vivante, prosodie spontanée, micro-variations de ton authentiques.'
    if extra:
        style += f' Intention spécifique demandée par le réalisateur : {extra}'
    out = opt('--out', 'voix'); os.makedirs(out, exist_ok=True)
    if opt('--text'):
        lines = [opt('--text')]
    else:
        lines = [l.rstrip('\n') for l in open(opt('--script'), encoding='utf-8') if l.strip()]
    state = {'rot': 0, 'meta': True}; man = []
    for i, line in enumerate(lines, 1):
        lid, txt = (line.split('|', 1) if '|' in line else (f'l{i}', line))
        lid, txt = lid.strip(), txt.strip()
        data, mime, used = tts(txt, voice, style, model_list, ks, state)
        path = os.path.join(out, f'{lid}.wav'); write_wav(path, data, mime)
        with wave.open(path) as w:
            dur = w.getnframes() / w.getframerate()
        man.append({'id': lid, 'file': path, 'text': txt, 'duration': round(dur, 3), 'voice': voice, 'model': used})
        print(f'{lid:6s} {dur:5.2f} s  [{used}]  {txt}')
    json.dump({'voice': voice, 'profile': prof, 'style': extra, 'lines': man}, open(os.path.join(out, 'manifest.json'), 'w'),
              ensure_ascii=False, indent=1)
    print(f'{len(man)} réplique(s) → {out}/manifest.json')


if __name__ == '__main__':
    main()
