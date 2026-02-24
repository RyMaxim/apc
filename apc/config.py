from apc.logging_config import get_logger

logger = get_logger(__name__)

import gettext
import json
import locale
import os
import random
import re
import sys
from enum import Enum
from pathlib import Path

from apc import __app_name__

SUPPORTED_LANGUAGES = ["en_US", "de_DE", "zh_CN", "ru_RU", "es_ES"]
default_locale = None

def get_languages() -> list:
  global default_locale
  default_locale, _ = locale.getdefaultlocale()
  env_language = os.environ.get("LANGUAGE")
  global use_languages
  if env_language:
    use_languages = env_language.split(':')
  else:
    use_languages = [default_locale]

  use_languages = list(filter(lambda x: x in SUPPORTED_LANGUAGES, use_languages))
  if len(use_languages) == 0:
    use_languages = ["en_US"]

  return (default_locale, use_languages)

LOCALE_PATH = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / "locale/"
_default, use_languages = get_languages()
t = gettext.translation("apc", localedir=LOCALE_PATH, languages=use_languages)
translate = t.gettext

def setup_translations() -> None:
  global APC
  APC = translate("Animal Population Changer")
  global SPECIES
  SPECIES = translate("Species")
  global ANIMALS_TITLE
  ANIMALS_TITLE = translate("Animals")
  global MALE
  MALE = translate("Male")
  global MALES
  MALES = translate("Males")
  global FEMALE
  FEMALE = translate("Female")
  global FEMALES
  FEMALES = translate("Females")
  global HIGH_WEIGHT
  HIGH_WEIGHT = translate("High Weight")
  global HIGH_SCORE
  HIGH_SCORE = translate("High Score")
  global LEVEL
  LEVEL = translate("Level")
  global GENDER
  GENDER = translate("Gender")
  global WEIGHT
  WEIGHT = translate("Weight")
  global SCORE
  SCORE = translate("Score")
  global VISUALSEED
  VISUALSEED = translate("Visual Seed")
  global FUR
  FUR = translate("Fur")
  global UNKNOWN
  UNKNOWN = translate("Unknown")
  global NONE
  NONE = translate("None")
  global BRONZE
  BRONZE = translate("Bronze")
  global SILVER
  SILVER = translate("Silver")
  global GOLD
  GOLD = translate("Gold")
  global DIAMOND
  DIAMOND = translate("Diamond")
  global GREATONE
  GREATONE = translate("Great One")
  global SUMMARY
  SUMMARY = translate("Summary")
  global RESERVE
  RESERVE = translate("Reserve")
  global RESERVES_TITLE
  RESERVES_TITLE = translate("Reserves")
  global RESERVE_NAME_KEY
  RESERVE_NAME_KEY = translate("Reserve Name (key)")
  global YES
  YES = translate("Yes")
  global NO
  NO = translate("No")
  global MODDED
  MODDED = translate("Modded")
  global SPECIES_NAME_KEY
  SPECIES_NAME_KEY = translate("Species (key)")
  global NEW_BUG
  NEW_BUG = translate("Please copy and paste as a new bug on Nexusmods here")
  global ERROR
  ERROR = translate("Error")
  global UNEXPECTED_ERROR
  UNEXPECTED_ERROR = translate("Unexpected Error")
  global WARNING
  WARNING = translate("Warning")
  global SAVED
  SAVED = translate("Saved")
  global DOES_NOT_EXIST
  DOES_NOT_EXIST = translate("does not exist")
  global FAILED_TO_BACKUP
  FAILED_TO_BACKUP = translate("failed to backup game")
  global FAILED_TO_LOAD_BACKUP
  FAILED_TO_LOAD_BACKUP = translate("failed to load backup file")
  global FAILED_TO_LOAD_MOD
  FAILED_TO_LOAD_MOD = translate("failed to load mod")
  global FAILED_TO_UNLOAD_MOD
  FAILED_TO_UNLOAD_MOD = translate("failed to unload mod")
  global MOD_LOADED
  MOD_LOADED = translate("Mod has been loaded")
  global MOD_UNLOADED
  MOD_UNLOADED = translate("Mod has been unloaded")
  global VERSION
  VERSION = translate("Version")
  global HUNTING_RESERVE
  HUNTING_RESERVE = translate("Hunting Reserve")
  global UPDATE_BY_PERCENTAGE
  UPDATE_BY_PERCENTAGE = translate("update by percentage")
  global MORE_MALES
  MORE_MALES = translate("More Males")
  global MORE_FEMALES
  MORE_FEMALES = translate("More Females")
  global GREATONES
  GREATONES = translate("More Great Ones")
  global DIAMONDS
  DIAMONDS = translate("More Diamonds")
  global INCLUDE_RARE_FURS
  INCLUDE_RARE_FURS = translate("include diamond rare furs")
  global ALL_FURS
  ALL_FURS = translate("All Furs")
  global RESET
  RESET = translate("Reset")
  global UPDATE_ANIMALS
  UPDATE_ANIMALS = translate("Update Animals")
  global JUST_FURS
  JUST_FURS = translate("Just the Furs")
  global ONE_OF_EACH_FUR
  ONE_OF_EACH_FUR = translate("one of each fur")
  global OTHERS
  OTHERS = translate("Others")
  global PARTY
  PARTY = translate("Party")
  global PARTY_DESCRIPTION
  PARTY_DESCRIPTION = translate("The sliders set the percentage of eligible animals to modify. Changes affect all species on the reserve.")
  global GREATONE_PARTY
  GREATONE_PARTY = translate("Great One Party")
  global GREATONE_PARTY_COMPLETE
  GREATONE_PARTY_COMPLETE = translate("of all eligible animals are Great Ones")
  global DIAMOND_PARTY
  DIAMOND_PARTY = translate("Diamond Party")
  global DIAMOND_PARTY_COMPLETE
  DIAMOND_PARTY_COMPLETE = translate("of all animals are Diamonds")
  # global WE_ALL_PARTY
  # WE_ALL_PARTY = translate("We All Party")
  global FUR_PARTY
  FUR_PARTY = translate("Random Fur Party")
  global FUR_PARTY_COMPLETE
  FUR_PARTY_COMPLETE = translate("of all animals have random furs")
  global RARE_FUR_PARTY
  RARE_FUR_PARTY = translate("Rare Fur Party")
  global RARE_FUR_PARTY_COMPLETE
  RARE_FUR_PARTY_COMPLETE = translate("of all animals have rare furs")
  global GENERATE_FUR_SEEDS
  GENERATE_FUR_SEEDS = translate("Generating fur seeds")
  global EXPLORE
  EXPLORE = translate("Explore")
  global DIAMONDS_AND_GREATONES
  DIAMONDS_AND_GREATONES = translate("diamonds and Great Ones")
  global LOOK_MODDED_ANIMALS
  LOOK_MODDED_ANIMALS = translate("look at modded animals")
  global LOOK_ALL_RESERVES
  LOOK_ALL_RESERVES = translate("look at all reserves")
  global ONLY_TOP_SCORES
  ONLY_TOP_SCORES = translate("only top 10 scores")
  global SHOW_ANIMALS
  SHOW_ANIMALS = translate("Show Animals")
  global FILES
  FILES = translate("Files")
  global FILE_NOT_FOUND
  FILE_NOT_FOUND = translate("The file could not be found")
  global MAP_DATA_NOT_FOUND
  MAP_DATA_NOT_FOUND = translate("Map data not found")
  global MAP_DATA_NOT_FOUND_INSTRUCTIONS
  MAP_DATA_NOT_FOUND_INSTRUCTIONS = translate("Open the game, load the map once, then save and quit. After that, reopen the mod tool and try again.")
  global CONFIGURE_GAME_PATH
  CONFIGURE_GAME_PATH = translate("Configure Game Path")
  global CONFIGURE_GAME_PATH_ERROR
  CONFIGURE_GAME_PATH_ERROR = translate("Please configure the path to your game save")
  global LIST_MODS
  LIST_MODS = translate("List Mods")
  global LOAD_MOD
  LOAD_MOD = translate("Load Mod")
  global UNLOAD_MOD
  UNLOAD_MOD = translate("Unload Mod")
  global SELECT_FOLDER
  SELECT_FOLDER = translate("Select the folder where the game saves your files")
  global SAVES_PATH_TITLE
  SAVES_PATH_TITLE = translate("Saves Path")
  global PATH_SAVED
  PATH_SAVED = translate("Game path saved")
  global CONFIRM_LOAD_MOD
  CONFIRM_LOAD_MOD = translate("Are you sure you want to overwrite your game file with the modded one?")
  global BACKUP_WILL_BE_MADE
  BACKUP_WILL_BE_MADE = translate("Don't worry, a backup copy will be made.")
  global CONFIRMATION
  CONFIRMATION = translate("Confirmation")
  global MOD
  MOD = translate("Mod")
  global VIEW_MODDED_VERSION
  VIEW_MODDED_VERSION = translate("View modded version")
  global VIEWING_LOADED_MOD
  VIEWING_LOADED_MOD = translate("viewing loaded")
  global VIEWING_MODDED
  VIEWING_MODDED = translate("viewing modded")
  global TOTAL_ANIMALS
  TOTAL_ANIMALS = translate("Total animals")
  global LOADED
  LOADED = translate("Loaded")
  global MODDED_FILE
  MODDED_FILE = translate("Modded File")
  global BACK_TO_RESERVE
  BACK_TO_RESERVE = translate("Back to Reserve")
  global UPDATE_TRANSLATIONS
  UPDATE_TRANSLATIONS = translate("update translations")
  global SWITCH_LANGUAGE
  SWITCH_LANGUAGE = translate("switch language")
  global PLEASE_RESTART
  PLEASE_RESTART = translate("Please restart to see changes")
  global DEFAULT
  DEFAULT = translate("default")
  global USING
  USING = translate("using")
  global OK
  OK = translate("OK")
  global CANCEL
  CANCEL = translate("Cancel")
  global MODIFY_ANIMALS
  MODIFY_ANIMALS = translate("Modify Animals")
  global GENDER_COUNTS
  GENDER_COUNTS = translate("Gender Counts")
  global ADD_REMOVE_ANIMALS
  ADD_REMOVE_ANIMALS = translate("Add/Remove Animals")
  global ADD_ANIMALS
  ADD_ANIMALS = translate("Adding Animals")
  global ADD_ANIMALS_ERROR
  ADD_ANIMALS_ERROR = translate("Can't add all animals")
  global TOO_MANY_GROUP_ANIMALS
  TOO_MANY_GROUP_ANIMALS = translate("Each group has a limit of 30 animals")
  global REMOVE_ANIMALS
  REMOVE_ANIMALS = translate("Removing Animals")
  global REMOVE_ANIMALS_ERROR
  REMOVE_ANIMALS_ERROR = translate("Can't remove animals")
  global TOO_FEW_GROUP_ANIMALS
  TOO_FEW_GROUP_ANIMALS = translate("Each group needs at least 1 animal")
  global TROPHY_RATING
  TROPHY_RATING = translate("Trophy Rating")
  global FURS
  FURS = translate("Furs")
  global MODIFY_ANIMAL_FURS
  MODIFY_ANIMAL_FURS = translate("Modify Animal Furs")
  global MALE_FURS
  MALE_FURS = translate("Male Furs")
  global FEMALE_FURS
  FEMALE_FURS = translate("Female Furs")
  global CHANGE_ALL_SPECIES
  CHANGE_ALL_SPECIES = translate("Change All Species")
  global EXPLORE_ANIMALS
  EXPLORE_ANIMALS = translate("Explore Animals")
  global MANAGE_MODDED_RESERVES
  MANAGE_MODDED_RESERVES = translate("Manage Modded Reserves")
  global USE_ALL_FURS
  USE_ALL_FURS = translate("use all furs")
  global ANIMAL_DETAILS
  ANIMAL_DETAILS = translate("Animal Details")
  global RANDOM_FUR
  RANDOM_FUR = translate("default is random fur")
  global UPDATE_ANIMAL
  UPDATE_ANIMAL = translate("Update Animal")
  global TOP_10
  TOP_10 = translate("Top 10")
  global LOADED_MOD
  LOADED_MOD = translate("Loaded")
  global EXPORT_MOD
  EXPORT_MOD = translate("Export Mod")
  global IMPORT_MOD
  IMPORT_MOD = translate("Import Mod")
  global EXPORT
  EXPORT = translate("Export")
  global IMPORT
  IMPORT = translate("Import")
  global EXPORT_MSG
  EXPORT_MSG = translate("Select the location and filename where you want to export")
  global IMPORT_MSG
  IMPORT_MSG = translate("Select the reserve mod to import")
  global EXPORT_AS
  EXPORT_AS = translate("Export As")
  global SELECT_FILE
  SELECT_FILE = translate("Select File")
  global MOD_EXPORTED
  MOD_EXPORTED = translate("Mod Exported")
  global MOD_IMPORTED
  MOD_IMPORTED = translate("Mod Imported")
  global SELECT_A_RESERVE
  SELECT_A_RESERVE = translate("No reserve data loaded. Select a reserve from the list.")
  global SELECT_AN_ANIMAL
  SELECT_AN_ANIMAL = translate("Select an animal from the list.")
  global LOADING_ANIMALS
  LOADING_ANIMALS = translate("Loading animals")
  global ANIMALS_LOADED
  ANIMALS_LOADED = translate("Animals loaded")
  global SELECTED_MULTIPLE_RESERVES
  SELECTED_MULTIPLE_RESERVES = translate("Selected animals from multiple reserves. Modifications will overwrite the following files:")
  global CLICK
  CLICK = translate("Click")
  global UPDATED_ANIMALS_ON_RESERVE
  UPDATED_ANIMALS_ON_RESERVE = translate("Updated animals on reserve")
  global UPDATED_ANIMALS_ON_RESERVE_2
  UPDATED_ANIMALS_ON_RESERVE_2 = translate("to load the modded file into your saves folder")
  global UPDATED_MULTIPLE_RESERVES
  UPDATED_MULTIPLE_RESERVES = translate("Updated animals on multiple reserves")
  global UPDATED_MULTIPLE_RESERVES_2
  UPDATED_MULTIPLE_RESERVES_2 = translate("to load the modded files for each reserve into your saves folder")
  global DONT_REMIND_ME
  DONT_REMIND_ME = translate("Don't remind me again")

setup_translations()

def update_language(locale: str) -> None:
  global use_languages
  use_languages = [locale]
  t = gettext.translation("apc", localedir=LOCALE_PATH, languages=use_languages)
  global translate
  translate = t.gettext
  setup_translations()

def _find_saves_path() -> Path:
    home_dir = Path.home()
    roots = [
      home_dir / "Documents" / "Avalanche Studios",
      home_dir / "OneDrive" / "Documents" / "Avalanche Studios",
    ]

    # Steam uses no subfolder → handle as empty string
    store_dirs = ["", "Epic Games Store", "Microsoft Store"]
    candidates = []
    for root in roots:
      for store in store_dirs:
        if store:
          candidates.append(root / store / "COTW" / "Saves")
        else:
          candidates.append(root / "COTW" / "Saves")

    base_saves = next((p for p in candidates if p.exists()), None)
    if not base_saves:
      logger.info("Unable to locate save directory")
      return None

    try:  # Find a numeric profile directory inside base_saves
      profile_dir = next(
        (p for p in base_saves.iterdir() if p.is_dir() and p.name.isdigit()),
        None,
      )
    except FileNotFoundError:
      logger.info("Unable to locate save directory")
      return None
    logger.info("Found save directory: %s", profile_dir)
    return profile_dir

def load_json(file: Path) -> dict:
  with open(file, "r", encoding="utf-8") as f:
    data = json.load(f)
  return data

APP_DIR_PATH = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
EXPORTS_PATH = APP_DIR_PATH / "exports"
EXPORTS_PATH.mkdir(exist_ok=True, parents=True)
DEFAULT_SAVE_PATH = _find_saves_path()
CONFIG_PATH = APP_DIR_PATH / "config"
SAVE_PATH = CONFIG_PATH / "save_path.txt"
SAVE_PATH.parent.mkdir(exist_ok=True, parents=True)
MOD_DIR_PATH = Path().cwd() / "mods"
MOD_DIR_PATH.mkdir(exist_ok=True, parents=True)
BACKUP_DIR_PATH = Path().cwd() / "backups"
BACKUP_DIR_PATH.mkdir(exist_ok=True, parents=True)
HIGH_NUMBER = 100000

ANIMAL_NAMES = load_json(CONFIG_PATH / "animal_names.json")
FUR_NAMES = load_json(CONFIG_PATH / "fur_names.json")
RESERVES = load_json(CONFIG_PATH / "reserve_details.json")
ANIMALS = load_json(CONFIG_PATH / "animal_details.json")
GLOBAL_ANIMAL_TYPES = CONFIG_PATH / "global_animal_types.blo"

# TODO: diamonds that can be both genders need different weight / score values

class Reserve(str, Enum):
   hirsch = "hirsch"
   layton = "layton"
   medved = "medved"
   vurhonga = "vurhonga"
   parque = "parque"
   yukon = "yukon"
   cuatro = "cuatro"
   silver = "silver"
   teawaroa = "teawaroa"
   rancho = "rancho"
   mississippi = "mississippi"
   revontuli = "revontuli"
   newengland = "newengland"
   emerald = "emerald"
   sundarpatan = "sundarpatan"
   salzwiesen = "salzwiesen"
   alberta = "alberta"
   scotland = "scotland"

class Strategy(str, Enum):
   great_one_all = "great-one-all"
   great_one_furs = "great-one-furs"
   great_one_some = "great-one-some"
   diamond_all = "diamond-all"
   diamond_furs = "diamond-furs"
   diamond_some = "diamond-some"
   males = "males"
   furs_some = "furs-some"
   females = "females"
   add = "add"
   remove = "remove"

class Levels(int, Enum):
  UNKNOWN = 0
  TRIVIAL = 1
  MINOR = 2
  VERY_EASY = 3
  EASY = 4
  MEDIUM = 5
  HARD = 6
  VERY_HARD = 7
  MYTHICAL = 8
  LEGENDARY = 9
  GREAT_ONE = 10

def get_level_name(level: Levels):
  if level == Levels.UNKNOWN:
    return translate("Unknown")
  if level == Levels.TRIVIAL:
   return translate("Trivial")
  if level == Levels.MINOR:
    return translate("Minor")
  if level == Levels.VERY_EASY:
    return translate("Very Easy")
  if level == Levels.EASY:
    return translate("Easy")
  if level == Levels.MEDIUM:
    return translate("Medium")
  if level == Levels.HARD:
    return translate("Hard")
  if level == Levels.VERY_HARD:
    return translate("Very Hard")
  if level == Levels.MYTHICAL:
    return translate("Mythical")
  if level == Levels.LEGENDARY:
    return translate("Legendary")
  if level == Levels.GREAT_ONE:
    return translate("Great One")
  return None

def get_difficulty(difficulty: str):
  match difficulty:
    case "Unknown":
      return 0
    case "Trivial":
      return 1
    case "Minor":
      return 2
    case "Very Easy":
      return 3
    case "Easy":
      return 4
    case "Medium":
      return 5
    case "Hard":
      return 6
    case "Very Hard":
      return 7
    case "Mythical":
      return 8
    case "Legendary":
      return 9
    case "Great One":
      return 10
    case _:
      return None

def load_config(config_path: Path) -> int:
  config_path.read_text()

def get_save_path() -> Path:
  if SAVE_PATH.exists():
    loaded_save_path = Path(SAVE_PATH.read_text())
    if loaded_save_path.exists():
      return loaded_save_path
    else:
      logger.warning("Unable to load from save path %s", loaded_save_path)
  return DEFAULT_SAVE_PATH

def write_save_path(save_path_location: str) -> None:
  SAVE_PATH.write_text(save_path_location)

def get_reserve_species_renames(reserve_key: str) -> dict:
  reserve = get_reserve(reserve_key)
  return reserve["renames"] if "renames" in reserve else {}

def get_species_name(species_key: str, star: bool = False) -> str:
  is_unique = species_unique_to_reserve(species_key)
  return F"{translate(ANIMAL_NAMES[species_key]['animal_name'])}{' ⭐' if is_unique and star else ''}"

def get_fur_name(key: str) -> str:
  if fur := FUR_NAMES.get(key):
    return translate(fur["fur_name"])
  else:
    logger.error(f"Unable to translate fur: {key}")
    return fur

def get_furs(species_key: str, gender: str, great_one: bool = None) -> list[str]:
  if (species_config := get_species(species_key)) is None:
    return []
  gender_key = f"great_one_{gender}" if great_one else gender
  gender_furs = sorted([fur for fur, probability in species_config["gender"][gender_key]["furs"].items() if probability > 0])  # exclude quest-only furs with 0 probability
  return gender_furs

def get_rare_furs(species_key: str, gender: str) -> list[str]:
  if (species_config := get_species(species_key)) is None:
    return []
  fur_total_probability = species_config["gender"][gender]["fur_total_probability"]
  gender_furs = species_config["gender"][gender]["furs"]
  '''
  "Rarity" values in `global_animal_types.blo` are inconsistent.
  Not worth adding/maintaining "rarity" values for each fur and muddying up the JSON.
  "Uncommon" is a difficult distinction. Should those be included as "rare" if they are fairly low percentage (eg <10%)?
  - Ring-Necked Pheasant: Mottling/Grey @ 12.5% are "common"
  - Himalayan Tahrs: Light Brown/Straw @ 12.5% are "uncommon"
  - Feral Goats: Black-Brown/Black-White/White-Brown @ 8.33% are "uncommon"
  - Water Buffalo Black @ 2-3% are "uncommon"
  All true "Rare" and "Very Rare" furs are below 1%
  '''
  rare_furs = [
    fur for fur, probability in gender_furs.items()
    if (
      probability > 0  # exclude quest-only furs with 0 probability
      and (probability/fur_total_probability) < 0.01  # This is 1%, not 0.01%
    )
  ]
  logger.debug(f"{species_key} :: {gender} >> {rare_furs}")
  return rare_furs

def species(reserve_key: str, include_keys = False) -> list:
  species_keys = RESERVES[reserve_key]["species"]
  return [f"{get_species_name(s)}{' (' + s + ')' if include_keys else ''}" for s in species_keys]

def get_species_key(species_name: str) -> str:
  for animal_name_key, names in ANIMAL_NAMES.items():
    if names["animal_name"] == species_name:
      return animal_name_key
  return None

def get_species_furs(species_key: str, gender: str, great_one: bool = None) -> list[str]:
  if gender == "both":
    males = get_furs(species_key, "male", great_one=great_one)
    females = get_furs(species_key, "female", great_one=great_one)
    return males + females
  else:
    return get_furs(species_key, gender, great_one=great_one)

def get_species_fur_names(species_key: str, gender: str, great_one: bool = None) -> dict[str, list[str]]:
  species_furs = get_species_furs(species_key, gender, great_one)
  return {"keys": [x for x in species_furs], "names": [get_fur_name(x) for x in species_furs]}

def get_reserve_species_name(species_key: str, reserve_key: str) -> str:
  renames = get_reserve_species_renames(reserve_key)
  species_key = renames[species_key] if species_key in renames else species_key
  return get_species_name(species_key, star=True)

def get_reserve_name(key: str) -> str:
  return translate(RESERVES[key]["reserve_name"])

def reserve_keys() -> list[str]:
  return list(dict.keys(RESERVES))

def reserve_names(include_keys = False) -> list[str]:
  keys = list(dict.keys(RESERVES))
  return [f"{get_reserve_name(r)}{' (' + r + ')' if include_keys else ''}" for r in keys]

def reserves() -> list[dict]:
  return [{"key": key, "name": name} for key, name in zip(reserve_keys(), reserve_names())]

def get_reserve_key_from_name(name: str) -> str:
  return reserve_keys()[reserve_names().index(name)]

def get_reserve(reserve_key: str) -> dict:
  return RESERVES[reserve_key]

def get_reserve_species(reserve_key: str) -> list:
  return get_reserve(reserve_key)["species"]

def get_species(species_key: str) -> dict:
  return ANIMALS.get(species_key, None)

def get_diamond_gender(species_key: str) -> str:
    if (species_config := get_species(species_key)) is None:
      return None
    diamond_min = species_config["trophy"]["diamond"]["score_low"]
    male_score = species_config["gender"]["male"]["score_high"]
    female_score = species_config["gender"]["female"]["score_high"]

    if male_score >= diamond_min and female_score >= diamond_min:
        return "both"
    if male_score >= diamond_min:
      return "male"
    if female_score >= diamond_min:
      return "female"
    logger.error(f"No valid Diamond genders for {species_key}")
    return None

def get_great_one_gender(species_key: str) -> str | None:
  if (species_config := get_species(species_key)) is None:
    return None
  keys = species_config["gender"].keys()
  great_one_keys = {k.removeprefix("great_one_") for k in keys if k.startswith("great_one_")}
  if not great_one_keys:
    return None
  return "both" if len(great_one_keys) == 2 else next(iter(great_one_keys))

def get_great_one_species(reserve_key: str) -> list[str]:
  great_one_species = []
  for species_key in get_reserve_species(reserve_key):
    if valid_great_one_species(species_key):
      great_one_species.append(species_key)
  return great_one_species

def get_safe_diamond_values(species_config: dict) -> dict[str, float]:
  '''
  Animals that use TruRACS antler/horn generation have some randomness in their scoring
  A TruRACS animal at the very low end of Diamond weight/score will often be a Gold due to an "imperfect" rack
  For TruRACS animals, add 20% padding to the low end of diamond values to increase the odds that we get diamonds
  Return regular values for non-TruRACS animals
  '''
  low_weight = species_config["trophy"]["diamond"]["weight_low"]
  high_weight =species_config["trophy"]["diamond"]["weight_high"]
  low_score = species_config["trophy"]["diamond"]["score_low"]
  high_score = species_config["trophy"]["diamond"]["score_high"]
  if species_config.get("truracs"):
    low_weight = min(low_weight, high_weight) + (0.2 * abs(high_weight - low_weight))
    low_score = min(low_score, high_score) + (0.2 * abs(high_score - low_score))
  return {"weight_low": low_weight, "score_low": low_score, "weight_high": high_weight, "score_high": high_score}

def generate_weight_and_score(gender_data, percentile: float = None, fuzz: bool = True) -> tuple[float, float]:
    '''
    Animals spawned by the game tend to have weight and score values in roughly the same percentile
    There is some variation of approximately to ±1% of the given range for randomness
    For example:
    - Male Whitetail Deer have a weight range of 59-100 and a score range of 71.2-275.5
    - A male Whitetail Deer with a weight of 79.5kg is in the 50th percentile (halfway between min/max weights)
    - That deer should have a score of roughly 173.35 (50th percentile, halfway between min/max scores)
    - 1% of the score range is ~2.04 points, so our 79.5kg male Whitetail Deer should have a score between 171.31-175.39
    '''
    weight_low = gender_data.get("weight_low")
    weight_high = gender_data.get("weight_high")
    score_low = gender_data.get("score_low")
    score_high = gender_data.get("score_high")
    if not percentile:
      percentile = random.uniform(0.01,1)
    weight_variation = random.uniform(-0.01, 0.01) * (weight_high - weight_low) if fuzz else 0
    weight = weight_low + percentile * (weight_high - weight_low) + weight_variation
    weight = max(weight_low, min(weight_high, weight))
    score_variation = random.uniform(-0.01, 0.01) * (score_high - score_low) if fuzz else 0
    score = score_low + percentile * (score_high - score_low) + score_variation
    score = max(score_low, min(score_high, score))
    return weight, score

def valid_species_for_reserve(species_key: str, reserve: str) -> bool:
  return reserve in RESERVES and species_key in RESERVES[reserve]["species"]

def valid_species(species_key: str) -> bool:
  return species_key in list(ANIMALS.keys())

def valid_great_one_species(species_key: str) -> bool:
    return get_great_one_gender(species_key) is not None

def valid_fur_species(species_key: str) -> bool:
  return True

def get_population_file_name(reserve_key: str):
    index = RESERVES[reserve_key]["index"]
    return f"animal_population_{index}"

def get_population_reserve_key(filename: str):
  for _reserve, details in RESERVES.items():
    reserve_filename = f"animal_population_{details['index']}"
    if reserve_filename == filename:
      return _reserve
  return None

def get_population_name(filename: str):
  for _reserve, details in RESERVES.items():
    reserve_filename = f"animal_population_{details['index']}"
    if reserve_filename == filename:
      return translate(details["reserve_name"])
  return None

def species_unique_to_reserve(species_key: str) -> bool:
  cnt = 0
  for _reserve_key, reserve_details in RESERVES.items():
    if species_key in reserve_details["species"]:
      cnt += 1
  return (cnt == 1)
