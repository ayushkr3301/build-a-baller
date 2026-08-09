"""Everything outside the Premier League: continental opposition and nations.

Only used by career mode. Strengths are on the same 0-100 scale as the domestic
clubs in clubs.py, so the same Poisson match model works unchanged.
"""

from typing import NamedTuple


class EuroClub(NamedTuple):
    id: str
    name: str
    short: str
    country: str
    attack: int
    defence: int


# Continental opposition for the Champions League and Europa League. English
# clubs are drawn from the real league table instead, so none appear here.
EURO_CLUBS: list[EuroClub] = [
    EuroClub("rma", "Real Madrid", "RMA", "Spain", 90, 84),
    EuroClub("bar", "Barcelona", "BAR", "Spain", 89, 82),
    EuroClub("bay", "Bayern Munich", "BAY", "Germany", 89, 83),
    EuroClub("psg", "Paris Saint-Germain", "PSG", "France", 87, 82),
    EuroClub("int", "Inter Milan", "INT", "Italy", 84, 85),
    EuroClub("atm", "Atletico Madrid", "ATM", "Spain", 80, 87),
    EuroClub("bvb", "Borussia Dortmund", "BVB", "Germany", 82, 76),
    EuroClub("juv", "Juventus", "JUV", "Italy", 79, 83),
    EuroClub("mil", "AC Milan", "MIL", "Italy", 80, 79),
    EuroClub("nap", "Napoli", "NAP", "Italy", 81, 80),
    EuroClub("ben", "Benfica", "BEN", "Portugal", 78, 76),
    EuroClub("por", "FC Porto", "POR", "Portugal", 77, 77),
    EuroClub("spo", "Sporting CP", "SPO", "Portugal", 78, 75),
    EuroClub("aja", "Ajax", "AJA", "Netherlands", 76, 72),
    EuroClub("psv", "PSV Eindhoven", "PSV", "Netherlands", 78, 73),
    EuroClub("fey", "Feyenoord", "FEY", "Netherlands", 75, 72),
    EuroClub("lev", "Bayer Leverkusen", "LEV", "Germany", 83, 79),
    EuroClub("rbl", "RB Leipzig", "RBL", "Germany", 80, 77),
    EuroClub("stu", "Stuttgart", "STU", "Germany", 76, 73),
    EuroClub("mon", "Monaco", "MON", "France", 77, 73),
    EuroClub("mar", "Marseille", "MAR", "France", 76, 72),
    EuroClub("lil", "Lille", "LIL", "France", 74, 74),
    EuroClub("ath", "Athletic Club", "ATH", "Spain", 76, 78),
    EuroClub("vil", "Villarreal", "VIL", "Spain", 76, 74),
    EuroClub("rso", "Real Sociedad", "RSO", "Spain", 74, 76),
    EuroClub("bet", "Real Betis", "BET", "Spain", 75, 73),
    EuroClub("ata", "Atalanta", "ATA", "Italy", 80, 76),
    EuroClub("rom", "Roma", "ROM", "Italy", 77, 78),
    EuroClub("laz", "Lazio", "LAZ", "Italy", 76, 76),
    EuroClub("gal", "Galatasaray", "GAL", "Turkey", 76, 72),
    EuroClub("fen", "Fenerbahce", "FEN", "Turkey", 75, 71),
    EuroClub("cel", "Celtic", "CEL", "Scotland", 72, 70),
    EuroClub("rbs", "Red Bull Salzburg", "RBS", "Austria", 71, 69),
    EuroClub("shk", "Shakhtar Donetsk", "SHK", "Ukraine", 72, 70),
    EuroClub("cop", "FC Copenhagen", "COP", "Denmark", 70, 69),
    EuroClub("clu", "Club Brugge", "CLU", "Belgium", 71, 70),
]

EURO_CLUB_BY_ID = {c.id: c for c in EURO_CLUBS}


class Nation(NamedTuple):
    id: str
    name: str
    short: str
    # 0-100 squad strength. Also the bar for getting into the squad: a weak nation
    # will cap a mediocre player, a strong one won't look at them.
    strength: int
    confederation: str


# Playable nationalities. Deliberately mixes powers with minnows -- 60 caps for
# Wales is a different career story from fighting for a Brazil shirt.
NATIONS: list[Nation] = [
    Nation("eng", "England", "ENG", 88, "UEFA"),
    Nation("fra", "France", "FRA", 90, "UEFA"),
    Nation("bra", "Brazil", "BRA", 89, "CONMEBOL"),
    Nation("arg", "Argentina", "ARG", 89, "CONMEBOL"),
    Nation("esp", "Spain", "ESP", 89, "UEFA"),
    Nation("ger", "Germany", "GER", 86, "UEFA"),
    Nation("por", "Portugal", "POR", 87, "UEFA"),
    Nation("ned", "Netherlands", "NED", 85, "UEFA"),
    Nation("ita", "Italy", "ITA", 84, "UEFA"),
    Nation("bel", "Belgium", "BEL", 82, "UEFA"),
    Nation("cro", "Croatia", "CRO", 81, "UEFA"),
    Nation("uru", "Uruguay", "URU", 82, "CONMEBOL"),
    Nation("col", "Colombia", "COL", 81, "CONMEBOL"),
    Nation("mar", "Morocco", "MAR", 80, "CAF"),
    Nation("sen", "Senegal", "SEN", 79, "CAF"),
    Nation("jpn", "Japan", "JPN", 78, "AFC"),
    Nation("kor", "South Korea", "KOR", 76, "AFC"),
    Nation("usa", "United States", "USA", 76, "CONCACAF"),
    Nation("mex", "Mexico", "MEX", 76, "CONCACAF"),
    Nation("den", "Denmark", "DEN", 79, "UEFA"),
    Nation("sui", "Switzerland", "SUI", 77, "UEFA"),
    Nation("aut", "Austria", "AUT", 77, "UEFA"),
    Nation("tur", "Turkey", "TUR", 76, "UEFA"),
    Nation("sco", "Scotland", "SCO", 73, "UEFA"),
    Nation("wal", "Wales", "WAL", 72, "UEFA"),
    Nation("irl", "Republic of Ireland", "IRL", 71, "UEFA"),
    Nation("nir", "Northern Ireland", "NIR", 66, "UEFA"),
    Nation("nga", "Nigeria", "NGA", 78, "CAF"),
    Nation("gha", "Ghana", "GHA", 75, "CAF"),
    Nation("civ", "Ivory Coast", "CIV", 77, "CAF"),
    Nation("nor", "Norway", "NOR", 76, "UEFA"),
    Nation("swe", "Sweden", "SWE", 75, "UEFA"),
    Nation("pol", "Poland", "POL", 76, "UEFA"),
    Nation("srb", "Serbia", "SRB", 77, "UEFA"),
    Nation("ukr", "Ukraine", "UKR", 75, "UEFA"),
    Nation("aus", "Australia", "AUS", 72, "AFC"),
    Nation("can", "Canada", "CAN", 74, "CONCACAF"),
    Nation("ecu", "Ecuador", "ECU", 76, "CONMEBOL"),
]

NATION_BY_ID = {n.id: n for n in NATIONS}

# Rivals for a nation at a major tournament, by confederation. UEFA nations meet
# UEFA nations at a Euros; everyone meets everyone at a World Cup.
UEFA_IDS = [n.id for n in NATIONS if n.confederation == "UEFA"]
