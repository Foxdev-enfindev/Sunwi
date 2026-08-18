import os
import re
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

# Top 100 - 2025
RAW_TOP_100_2025 = """
1 Jin Don't Say You Love Me
2 Jennie Like Jennie
3 Blackpink Jump
4 Lisa Born Again
5 Jennie Extra L
6 Twice Takedown
7 j-hope Killin' It Girl (feat. GloRilla)
8 j-hope Mona Lisa
9 Jennie Love Hangover
10 Jennie Handlebars
11 j-hope Sweet Dreams (feat. Miguel)
12 Jisoo Earthquake
13 Rosé Messy
14 LE SSERAFIM Hot
15 Jennie Seoul City
16 LE SSERAFIM Spaghetti
17 Twice This is For
18 Jisoo EYES CLOSED (with ZAYN)
19 Ten Stunner
20 TXT Beautiful Strangers
21 Rosé On My Mind
22 j-hope Killin' It Girl (Solo Version)
23 Cortis GO!
24 ILLIT Do The Dance
25 NCT Dream Chiller
26 Lisa FXCK UP THE WORLD (feat. Future)
27 Stray Kids Ceremony
28 Hearts2Hearts The Chase
29 Cortis Fashion
30 Enhypen Bad Desire (With or Without You)
31 Meovv Hands Up
32 aespa Dirty Work
33 Jennie with the IE (way up)
34 IVE Rebel Heart
35 ILLIT jellyous
36 TXT Love Language
37 Jennie Damn Right
38 Hearts2Hearts Style
39 Lisa Dream
40 Jennie Zen
41 LE SSERAFIM Come Over
42 IVE Attitude
43 AllDay Project Famous
44 Jennie start a war
45 Jisoo Your Love
46 Lisa Chill
47 aespa Rich Man
48 RM Stop the Rain
49 ILLIT Not Cute Anymore
50 XLOV 1&Only
51 BOYNEXTDOOR If I Say, I Love You
52 Enhypen Loose
53 G-Dragon Too Bad
54 Jin Nothing Without Your Love
55 Stray Kids Truman (HAN and Felix)
56 Babymonster Hot Sauce
57 Jin Loser
58 Babymonster We Go Up
59 GOT7 Python
60 Stray Kids Do It
61 Lisa When I'm With You (feat. Tyla)
62 Jin Rope It
63 Jin Background
64 Jin Close to You
65 Enhypen Outside
66 Ateez In Your Fantasy
67 Stray Kids ESCAPE (Bang Chan & Hyunjin)
68 Jin With the Clouds
69 Enhypen Bad Desire (With or Without You) (English Ver.)
70 IVE xoxz
71 Jin To Me, Today
72 AllDay Project Wicked
73 Beomgyu Panic
74 Ateez Lemon Drop
75 Lisa Lifestyle
76 BSS Prime Time
77 Lisa FXCK UP THE WORLD (Vixi Solo Version)
78 Cortis What You Want
79 TXT Ghost Girl
80 Jennie twin
81 Stray Kids Bleep
82 LE SSERAFIM Ash
83 Jennie Filter
84 Jisoo Hugs & Kisses
85 BTS Permission to Dance - Live
86 Stray Kids Creed
87 Jennie Starlight
88 NMIXX Know About Me
89 Cortis JoyRide
90 Stray Kids Divine
91 Yeonjun Talk to You
92 Seventeen Thunder
93 Lisa Thunder
94 Lisa Elastigirl
95 NMIXX Blue Valentine
96 Stray Kids Burnin’ Tires (Changbin & I.N)
97 Enhypen Helium
98 Stray Kids CINEMA (Lee Know & Seungmin)
99 ZEROBASEONE Doctor! Doctor!
100 Treasure Yellow
"""

# Top 100 - 2024
RAW_TOP_100_2024 = """
1 Jimin Who
2 Rosé Apt.
3 ILLIT Magnetic
4 V FRI(END)S
5 Lisa Rockstar
6 LE SSERAFIM Smart
7 BABYMONSTER Sheesh
8 Lisa New Woman
9 aespa Supernova
10 LE SSERAFIM Easy
11 Lisa Moonlit Floor
12 Jennie Mantra
13 KATSEYE Touch
14 Jimin Smeraldo Garden Marching Band
15 Zico and Jennie Spot!
16 aespa Armageddon
17 Jimin Be Mine
18 Stray Kids Chk Chk Boom
19 Jin Running Wild
20 Jungkook Never Let Go
21 TXT Deja Vu
22 LE SSERAFIM Crazy
23 NewJeans How Sweet
24 Jin I'll Be There
25 j-hope Neuron
26 RM Neva Play
27 Ten Nightwalker
28 NewJeans Supernatural
29 aespa Whiplash
30 RM Lost!
31 Huh Yunjin Stupid in Love
32 BABYMONSTER Like That
33 Kiss of Life Midas Touch
34 V Winter Ahead
35 BABYMONSTER Forever
36 Kiss of Life Sticky
37 NCT Dream Smoothie
38 Nayeon ABCD
39 IU Love Wins All
40 (G)I-DLE Super Lady
41 Seventeen Maestro
42 Rosé number one girl
43 XG Woke Up
44 ENHYPEN XO (Only If You Say Yes)
45 NewJeans Bubble Gum
46 (G)I-DLE Wife
47 Twice One Spark
48 RM Come Back To Me
49 ILLIT Lucky Girl Syndrome
50 Rosé toxic till the end
51 Twice I Got You
52 IVE HEYA
53 aespa Up
54 Kiss of Life Igloo
55 BABYMONSTER Drip
56 10CM Spring Snow
57 j-hope and Jungkook I wonder…
58 Stray Kids Lose My Breath
59 Jimin Slow Dance
60 Yeonjun Ggum
61 TWS Plot Twist
62 Stray Kids I Like It
63 Crush Love You With All My Heart
64 RIIZE Love 119
65 Ateez Work
66 NMIXX Dash
67 Jimin Rebirth (Intro)
68 Stray Kids Come Play
69 Itzy Untouchable
70 KATSEYE Debut
71 (G)I-DLE Fate
72 Jin Super Tuna
73 Lee Young Ji and D.O. Small Girl
74 Taeyong Tap
75 ENHYPEN Brought The Heat Back
76 Red Velvet Cosmic
77 BSS The Reasons of my Smile
78 BIBI Bam Yang Gang
79 ILLIT Cherish (My Love)
80 TXT I’ll See You There Tomorrow
81 ENHYPEN Fatal Trouble
82 Jimin Interlude: Showtime
83 V White Christmas
84 MEOVV MEOW
85 Stray Kids JJAM
86 LE SSERAFIM 1-800-hot-n-fun
87 TXT Over The Moon
88 NewJeans Right Now
89 RIIZE Boom Boom Bass
90 LE SSERAFIM Swan Song
91 Lisa Rockstar - Extended
92 ENHYPEN Moonstruck
93 XG Something Ain't Right
94 Seventeen Love, Money, Fame
95 (G)I-DLE Klaxon
96 NCT Dream When I'm With You
97 BOYNEXTDOOR Earth, Wind & Fire
98 ILLIT Midnight Fiction
99 Stray Kids Mountains
100 IVE Accendio
"""

# Top 100 - 2023
RAW_TOP_100_2023 = """
1 Jungkook Seven
2 Jisoo Flower
3 Stray Kids S-Class
4 Kai Rover
5 Fifty Fifty Cupid (Twin Version)
6 (G)I-DLE Queencard
7 IVE I Am
8 XG Shooting Star
9 Ateez Bouncy
10 Taeyang with Jimin Vibe
11 MAVE Pandora
12 Lee Chaeyeon Knock
13 Jimin Like Crazy
14 Jennie One of the Girls
15 TWICE Moonlight Sunrise
16 aespa Spicy
17 Fifty Fifty Cupid
18 (G)I-DLE Allergy
19 IVE Kitsch
20 XG Left Right
21 Taeyang with Lisa Shoong!
22 NewJeans OMG
23 Jisoo All Eyes On Me
24 TWICE Set Me Free
25 aespa Hold On Tight
26 IVE Baddie
27 Somi Fast Forward
28 NewJeans Super Shy
29 Jennie You & Me
30 NMIXX Love Me Like This
31 NCT Dojaejung Perfume
32 Jungkook 3D
33 Blackpink The Girls
34 Stray Kids LALALALA
35 aespa Better Things
36 V Love Me Again
37 Jennie You & Me (Coachella Ver)
38 ITZY Cake
39 Baekhyun Paranoia
40 Jimin Like Crazy (English Version)
41 Stray Kids Topline
42 aespa Drama
43 Jimin Set Me Free Pt. 2
44 Jihyo Killin' Me Good
45 NCT Dream Broken Melodies
46 V Slow Dancing
47 MISAMO Do not touch
48 EXO Cream Soda
49 Jungkook Standing Next To You
50 Stray Kids Super Bowl
51 BTS Take Two
52 Stray Kids Hall of Fame
53 Agust D Haegeum
54 Jimin Angel Pt. 1
55 ENHYPEN Bite Me
56 V Rainy Days
57 LE SSERAFIM Unforgiven
58 NewJeans New Jeans
59 j-hope On The Street
60 Seventeen Super
61 Agust D People Pt. 2
62 TXT Sugar Rush Ride
63 NewJeans ETA
64 LE SSERAFIM Eve, Psyche & The Bluebeard's Wife
65 NewJeans Cool With You
66 TXT Tinnitus
67 Jimin Face-off
68 Jungkook Too Much
69 LE SSERAFIM Perfect Night
70 Jimin Alone
71 SUGA Lilith
72 BTS The Planet
73 NewJeans Get Up
74 NewJeans ASAP
75 NewJeans Gods
76 TXT Do It Like That
77 BSS Fighting
78 Jimin Angel Pt. 2
79 V Slow Dancing (Piano Ver)
80 V For Us
81 RM Smoke Sprite
82 Jungkook Yes or No
83 V Blue
84 Jimin Interlude: Dive
85 TXT Devil By The Window
86 TXT Back For More
87 NewJeans Zero
88 Agust D Amygdala
89 TXT Farewell Neverland
90 Jungkook Hate You
91 RM Don't Ever Say Love Me
92 Jungkook Please Don't Change
93 Agust D D-Day
94 Jimin Angel Pt. 1 (Trailer Version)
95 Jungkook Closer To You
96 Seventeen I Don't Understand But I Love U
97 Seventeen F*ck My Life
98 Agust D Snooze
99 Jungkook Somebody
100 ENHYPEN Sacrifice
"""

# Top 100 - 2022
RAW_TOP_100_2022 = """
1 LOVE DIVE IVE
2 TOMBOY (G)I-DLE
3 DrunKen Confession Kim MinSeok (MeloMance)
4 Love, Maybe MeloMance
5 Love Always Runs Away Lim Young Woong
6 ELEVEN IVE
7 Still Life BIGBANG
8 If you lovingly call my name GyeongseoYeji, Jeon Gunho
9 That That (prod. & feat. SUGA of BTS) PSY
10 Beyond Love (Feat. 10CM) BIG Naughty
11 Traffic Light Lee Mujin
12 INVU TAEYEON
13 Merry-Go-Round (Feat. Zion.T, Wonstein) (Prod. Slom) sokodomo
14 Feel My Rhythm Red Velvet
15 Hype Boy NewJeans
16 GANADARA (Feat. IU) Jay Park
17 Attention NewJeans
18 After LIKE IVE
19 Dear my X KyoungSeo
20 At That Moment WSG WANNABE (Gaya-G)
21 LOVE me BE'O
22 Next Level aespa
23 Limousine (Feat. MINO) (Prod. GRAY) BE'O
24 Drama IU
25 Strawberry Moon IU
26 Every moment of you Sung Si Kyung
27 without me Juho
28 Do you want to hear MSG WANNABE (M.O.M)
29 Think About You Joosiq
30 Dynamite BTS
31 I Missed You WSG WANNABE (4FIRE)
32 SMILEY (Feat. BIBI) YENA
33 Weekend TAEYEON
34 FEARLESS LE SSERAFIM
35 Butter BTS
36 Pink Venom BLACKPINK
37 Always love you Kassy
38 Shiny Star (2020) KyoungSeo
39 New Thing (Prod. ZICO) (Feat. Homies) ZICO
40 Counting Stars (Feat. Beenzino) BE'O
41 Every Day, Every Moment Paul Kim
42 When it snows (Feat. Heize) Lee Mujin
43 Trust in Me Lim Young Woong
44 OHAYO MY NIGHT D-Hack, PATEKO
45 Hold my hand IU
46 Permission to Dance BTS
47 Our Blues, Our Life Lim Young Woong
48 Foolish Love MSG WANNABE (M.O.M)
49 Event Horizon YOUNHA
50 Step Back GOT the beat
51 Celebrity IU
52 MY BAG (G)I-DLE
53 Savage aespa
54 POP! NAYEON (TWICE)
55 Gradation 10CM
56 Horangsuwolga Tophyun
57 LILAC IU
58 Spring Day BTS
59 Suddenly BE'O
60 Dreams Come True aespa
61 How can I love the heartbreak, you're the one I love AKMU
62 Love story BOL4
63 Meeting is easy, parting is hard (Feat. Leellamarz) (Prod. TOIL) Basick
64 Siren Remix (Feat. UNEDUCATED KID, Paul Blanco) Homies
65 Baby I Need You Joosiq
66 Haeyo (2022) An Nyeong
67 Blueming IU
68 The Eternal Moment MAKTUB
69 RUN2U STAYC
70 Go Back MeloMance
71 SNEAKERS ITZY
72 Rollin' Brave Girls
73 HAPPEN Heize
74 Cookie NewJeans
75 If We Ever Meet Again Lim Young Woong
76 FOREVER 1 Girls' Generation
77 Winter Sleep IU
78 Shut Down BLACKPINK
79 Nxde (G)I-DLE
80 Dun Dun Dance OH MY GIRL
81 Drawer 10CM
82 Illusion aespa
83 Twenty-five, twenty-one JAURIM
84 ANTIFRAGILE LE SSERAFIM
85 Don't wanna leave tonight Kassy
86 NAKKA (with IU) AKMU
87 ZOOM Jessi
88 Girls aespa
89 Rush Hour (Feat. j-hope of BTS) Crush
90 My Pleasure Is That You Ride The Bentley Kim Seungmin
91 You, you (Nth Romance X Whee In) Whee In
92 Yet To Come BTS
93 Christmas Tree V
94 Rainbow Lim Young Woong
95 Monologue Tei
96 To You My Light (Feat. Lee Raon) MAKTUB
97 Your Existence Wonstein
98 Slightly Tipsy (She is My Type♡ X SANDEUL) Sandeul
99 Maybe If BIBI
100 I Still Love You Jung Dong Ha
"""

# Regroupement des artistes connus / complexes pour faciliter l'analyse
KNOWN_ARTISTS = [
    "LE SSERAFIM", "(G)I-DLE", "Stray Kids", "BABYMONSTER", "Kiss of Life",
    "NewJeans", "NCT Dream", "Red Velvet", "BOYNEXTDOOR", "Lee Young Ji and D.O.",
    "Zico and Jennie", "j-hope and Jungkook", "Huh Yunjin", "Rosé & Bruno Mars",
    "Taeyang with Jimin", "Taeyang with Lisa", "Kim MinSeok", "Lim Young Woong", 
    "GyeongseoYeji, Jeon Gunho", "BIG Naughty", "Lee Mujin", "sokodomo", "Jay Park", 
    "WSG WANNABE (Gaya-G)", "BE'O", "Sung Si Kyung", "MSG WANNABE (M.O.M)", 
    "WSG WANNABE (4FIRE)", "Kassy", "KyoungSeo", "ZICO", "Paul Kim", "D-Hack, PATEKO", 
    "YOUNHA", "GOT the beat", "NAYEON (TWICE)", "10CM", "Tophyun", "AKMU", "BOL4", 
    "Basick", "Homies", "Joosiq", "An Nyeong", "MAKTUB", "STAYC", "MeloMance", 
    "ITZY", "Brave Girls", "Heize", "Girls' Generation", "OH MY GIRL", "JAURIM", 
    "Jessi", "Crush", "Kim Seungmin", "Whee In", "Tei", "Sandeul", "BIBI", "Jung Dong Ha"
]

def parse_entry(line):
    line = re.sub(r'^\d+\s+', '', line.strip())
    for known in KNOWN_ARTISTS:
        if line.startswith(known):
            title = line[len(known):].strip()
            return known, title

    parts = line.split(' ', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return line, line

def fetch_deezer_info(artist, title):
    try:
        query = f'artist:"{artist}" track:"{title}"'
        res = requests.get('https://api.deezer.com/search', params={'q': query}, timeout=5)
        data = res.json().get('data', [])

        if not data:
            res = requests.get('https://api.deezer.com/search', params={'q': f'{artist} {title}'}, timeout=5)
            data = res.json().get('data', [])

        if data and data[0].get('preview'):
            return {
                'id': str(data[0]['id']),
                'name': data[0].get('title_short') or data[0].get('title'),
                'artist': data[0]['artist']['name'],
                'cover_url': data[0]['album']['cover_big'],
                'preview_url': data[0]['preview']
            }
    except Exception as e:
        print(f"⚠️ Erreur Deezer ({artist} - {title}): {e}")
    return None

def populate_top100_spotify(genre='kpop', year=2024, raw_text=RAW_TOP_100_2024):
    if not DATABASE_URL:
        print("❌ DATABASE_URL manquante dans le .env")
        return

    lines = [l.strip() for l in raw_text.strip().split('\n') if l.strip()]
    print(f"📋 {len(lines)} titres prêts pour l'importation ({genre.upper()} {year}).")

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()

    cur.execute("DELETE FROM top100_tracks WHERE genre = %s AND year = %s;", (genre, year))
    conn.commit()

    inserted = 0
    skipped = 0

    for idx, line in enumerate(lines, start=1):
        artist, title = parse_entry(line)
        deezer_data = fetch_deezer_info(artist, title)

        if not deezer_data:
            print(f"⚠️ [{idx}/100] Non trouvé sur Deezer : {artist} - {title}")
            skipped += 1
            continue

        cur.execute("""
            INSERT INTO top100_tracks (track_id, genre, year, name, artist, country, cover_url, preview_url)
            VALUES (%s, %s, %s, %s, %s, 'KR', %s, %s)
            ON CONFLICT (track_id, genre, year) DO NOTHING;
        """, (deezer_data['id'], genre, year, deezer_data['name'], deezer_data['artist'], deezer_data['cover_url'], deezer_data['preview_url']))

        inserted += 1
        print(f"  [{inserted}/100] Ajouté : {deezer_data['artist']} - {deezer_data['name']}")

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n✅ Importation {year} terminée : {inserted} titres insérés avec succès ({skipped} ratés) !")

if __name__ == '__main__':
    # Décommente l'année que tu souhaites importer :
    
     populate_top100_spotify('kpop', 2022, RAW_TOP_100_2022)
    # populate_top100_spotify('kpop', 2023, RAW_TOP_100_2023)
    # populate_top100_spotify('kpop', 2024, RAW_TOP_100_2024)
    #  populate_top100_spotify('kpop', 2025, RAW_TOP_100_2025)