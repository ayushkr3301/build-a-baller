"""The 20 Premier League clubs of the 2025/26 season, plus EFL sides for the FA Cup.

`attack` / `defence` are 0-100 strength ratings that feed the Poisson match model.
`prestige` drives how likely the club is to come up on a weighted club spin.
"""

from typing import NamedTuple


class Club(NamedTuple):
    id: str
    name: str
    short: str
    attack: int
    defence: int
    prestige: int
    primary: str
    secondary: str


CLUBS: list[Club] = [
    Club("mci", "Manchester City", "MCI", 89, 82, 96, "#6CABDD", "#1C2C5B"),
    Club("liv", "Liverpool", "LIV", 88, 84, 95, "#C8102E", "#00B2A9"),
    Club("ars", "Arsenal", "ARS", 85, 88, 93, "#EF0107", "#063672"),
    Club("che", "Chelsea", "CHE", 83, 80, 90, "#034694", "#DBA111"),
    Club("mun", "Manchester United", "MUN", 76, 74, 92, "#DA291C", "#FBE122"),
    Club("tot", "Tottenham Hotspur", "TOT", 78, 72, 84, "#132257", "#FFFFFF"),
    Club("new", "Newcastle United", "NEW", 80, 79, 82, "#241F20", "#FFFFFF"),
    Club("avl", "Aston Villa", "AVL", 78, 78, 79, "#95BFE5", "#670E36"),
    Club("bha", "Brighton & Hove Albion", "BHA", 76, 73, 74, "#0057B8", "#FFCD00"),
    Club("whu", "West Ham United", "WHU", 70, 66, 74, "#7A263A", "#1BB1E7"),
    Club("eve", "Everton", "EVE", 68, 74, 72, "#003399", "#FFFFFF"),
    Club("cry", "Crystal Palace", "CRY", 74, 76, 70, "#1B458F", "#C4122E"),
    Club("nfo", "Nottingham Forest", "NFO", 74, 74, 70, "#DD0000", "#FFFFFF"),
    Club("ful", "Fulham", "FUL", 72, 73, 69, "#FFFFFF", "#000000"),
    Club("bou", "AFC Bournemouth", "BOU", 75, 74, 68, "#DA291C", "#000000"),
    Club("bre", "Brentford", "BRE", 73, 71, 68, "#E30613", "#FBB800"),
    Club("lee", "Leeds United", "LEE", 66, 65, 68, "#FFCD00", "#1D428A"),
    Club("wol", "Wolverhampton Wanderers", "WOL", 68, 66, 66, "#FDB913", "#231F20"),
    Club("sun", "Sunderland", "SUN", 64, 66, 63, "#EB172B", "#FFFFFF"),
    Club("bur", "Burnley", "BUR", 62, 64, 60, "#6C1D45", "#99D6EA"),
]

CLUB_BY_ID = {c.id: c for c in CLUBS}

# Lower-league opposition to pad the FA Cup bracket out to 32 teams.
EFL_CLUBS: list[Club] = [
    Club("lei", "Leicester City", "LEI", 60, 58, 55, "#003090", "#FDBE11"),
    Club("sou", "Southampton", "SOU", 58, 56, 52, "#D71920", "#FFFFFF"),
    Club("ips", "Ipswich Town", "IPS", 57, 57, 50, "#3A64A3", "#FFFFFF"),
    Club("nor", "Norwich City", "NOR", 56, 54, 48, "#FFF200", "#00A650"),
    Club("wba", "West Bromwich Albion", "WBA", 55, 57, 47, "#122F67", "#FFFFFF"),
    Club("mid", "Middlesbrough", "MID", 56, 56, 46, "#E21C38", "#FFFFFF"),
    Club("cov", "Coventry City", "COV", 57, 54, 45, "#78D0F3", "#000000"),
    Club("shw", "Sheffield Wednesday", "SHW", 52, 53, 44, "#0066B3", "#FFFFFF"),
    Club("mil", "Millwall", "MIL", 51, 55, 40, "#001D5B", "#FFFFFF"),
    Club("prs", "Preston North End", "PRE", 50, 53, 38, "#B2B2B2", "#FFFFFF"),
    Club("wyc", "Wycombe Wanderers", "WYC", 46, 48, 30, "#003399", "#87CEEB"),
    Club("spt", "Stockport County", "SPT", 44, 46, 27, "#003DA5", "#FFFFFF"),
]

ALL_CUP_CLUBS = CLUBS + EFL_CLUBS
CUP_CLUB_BY_ID = {c.id: c for c in ALL_CUP_CLUBS}

# Display-only badges for legends whose club no longer sits in the modern top flight.
# These never enter the simulation -- they only label a legend's card on a spin.
LEGACY_CLUBS: list[Club] = [
    Club("blb", "Blackburn Rovers", "BLB", 0, 0, 0, "#009EE0", "#FFFFFF"),
    Club("bol", "Bolton Wanderers", "BOL", 0, 0, 0, "#263C7E", "#FFFFFF"),
    Club("por", "Portsmouth", "POR", 0, 0, 0, "#001489", "#FFFFFF"),
    Club("qpr", "Queens Park Rangers", "QPR", 0, 0, 0, "#1D5BA4", "#FFFFFF"),
    Club("cha", "Charlton Athletic", "CHA", 0, 0, 0, "#D4021D", "#FFFFFF"),
    Club("wig", "Wigan Athletic", "WIG", 0, 0, 0, "#1D59AF", "#FFFFFF"),
    Club("rea", "Reading", "REA", 0, 0, 0, "#004494", "#FFFFFF"),
    Club("der", "Derby County", "DER", 0, 0, 0, "#000000", "#FFFFFF"),
    Club("bir", "Birmingham City", "BIR", 0, 0, 0, "#0000FF", "#FFFFFF"),
    Club("stk", "Stoke City", "STK", 0, 0, 0, "#E03A3E", "#FFFFFF"),
    Club("swa", "Swansea City", "SWA", 0, 0, 0, "#121212", "#FFFFFF"),
    Club("hul", "Hull City", "HUL", 0, 0, 0, "#F5A12D", "#000000"),
    Club("wat", "Watford", "WAT", 0, 0, 0, "#FBEE23", "#ED2127"),
    Club("shu", "Sheffield United", "SHU", 0, 0, 0, "#EE2737", "#000000"),
    Club("bpl", "Blackpool", "BPL", 0, 0, 0, "#F68712", "#FFFFFF"),
    Club("wim", "Wimbledon", "WIM", 0, 0, 0, "#001489", "#FFD100"),
]

# Everything that can appear on a player card, simulated or not.
DISPLAY_CLUB_BY_ID = {c.id: c for c in CLUBS + EFL_CLUBS + LEGACY_CLUBS}
