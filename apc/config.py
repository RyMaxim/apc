import os
import re
import json
import sys
from pathlib import Path
from enum import Enum
from apc import __app_name__, t

translate = t.gettext

def _find_saves_path() -> str:
    steam_saves = Path().home() / "Documents/Avalanche Studios/COTW/Saves"
    steam_onedrive = Path().home() / "OneDrive/Documents/Avalanche Studios/COTW/Saves"
    epic_saves = Path().home() / "Documents/Avalanche Studios/Epic Games Store/COTW/Saves"
    epic_onedrive = Path().home() / "OneDrive/Documents/Avalanche Studios/Epic Games Store/COTW/Saves"
    
    base_saves = None
    if steam_saves.exists():
      base_saves = steam_saves
    elif epic_saves.exists():
      base_saves = epic_saves
    elif steam_onedrive.exists():
      base_saves = steam_onedrive
    elif epic_onedrive.exists():
      base_saves = epic_onedrive      

    save_folder = None
    if base_saves:
        folders = os.listdir(base_saves)
        all_numbers = re.compile(r"\d+")
        for folder in folders:
            if all_numbers.match(folder):
                save_folder = folder
                break
    if save_folder:
       return base_saves / save_folder
    else:
      return None

APP_DIR_PATH = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
DEFAULT_SAVE_PATH = _find_saves_path()
CONFIG_PATH = APP_DIR_PATH / "config"
SAVE_PATH = CONFIG_PATH / "save_path.txt"
SAVE_PATH.parent.mkdir(exist_ok=True, parents=True)
MOD_DIR_PATH = Path().cwd() / "mods"
MOD_DIR_PATH.mkdir(exist_ok=True, parents=True)
BACKUP_DIR_PATH = Path().cwd() / "backups"
BACKUP_DIR_PATH.mkdir(exist_ok=True, parents=True)
HIGH_NUMBER = 100000

ANIMAL_NAMES = json.load((CONFIG_PATH / "animal_names.json").open())["animal_names"]
RESERVE_NAMES = json.load((CONFIG_PATH / "reserve_names.json").open())["reserve_names"]
RESERVES = json.load((CONFIG_PATH / "reserve_details.json").open())
ANIMALS = json.load((CONFIG_PATH / "animal_details.json").open())

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

class Strategy(str, Enum):
   go_all = "go-all"
   go_furs = "go-furs"
   go_some = "go-some"
   diamond_all = "diamond-all"
   diamond_furs = "diamond-furs"
   diamond_some = "diamond-some"
   males = "males"
   furs = "furs"
   furs_some = "furs-some"
   females = "females"

class GreatOnes(str, Enum):
   moose = "moose"
   black_bear = "black_bear"
   whitetail_deer = "whitetail_deer"
   red_deer = "red_deer"

class Levels(int, Enum):
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

SPECIES = translate("Species")
ANIMALS_TITLE = translate("Animals")
MALE = translate("Male")
MALES = translate("Males")
FEMALE = translate("Female")
FEMALES = translate("Females")
HIGH_WEIGHT = translate("High Weight")
HIGH_SCORE = translate("High Score")
LEVEL = translate("Level")
GENDER = translate("Gender")
WEIGHT = translate("Weight")
SCORE = translate("Score")
VISUALSEED = translate("Visual Seed")
FUR = translate("Fur")
DIAMOND = translate("Diamond")
GREATONE = translate("Great One")
SUMMARY = translate("Summary")
RESERVE = translate("Reserve")
RESERVES_TITLE = translate("Reserves")
RESERVE_NAME_KEY = translate("Reserve Name (key)")
YES = translate("Yes")
MODDED = translate("Modded")
SPECIES_NAME_KEY = translate("Species (key)")

def format_key(key: str) -> str:
  key = [s.capitalize() for s in re.split("_|-", key)]
  return " ".join(key)

def load_config(config_path: Path) -> int: 
  config_path.read_text()

def get_save_path() -> Path:
  if SAVE_PATH.exists():
    return Path(SAVE_PATH.read_text())
  return DEFAULT_SAVE_PATH

def save_path(save_path_location: str) -> None:
  SAVE_PATH.write_text(save_path_location)

def get_reserve_species_renames(reserve_key: str) -> dict:
  reserve = get_reserve(reserve_key)
  return reserve["renames"] if "renames" in reserve else {}

def get_species_name(key: str) -> str:
  return translate(ANIMAL_NAMES[key]["animal_name"])

def get_species_key(species_name: str) -> str:
  for animal_name_key, names in ANIMAL_NAMES.items():
    if names["animal_name"] == species_name:
      return animal_name_key
  return None

def get_reserve_species_name(species_key: str, reserve_key: str) -> str:
  renames = get_reserve_species_renames(reserve_key)
  species_key = renames[species_key] if species_key in renames else species_key
  return get_species_name(species_key)

def get_reserve_species_key(species_name: str, reserve_key: str) -> str:
  reserve = get_reserve(reserve_key)
  species_key = get_species_key(species_name)
  if species_key in reserve["species"]:
    return species_key
  renames = get_reserve_species_renames(reserve_key)
  for name, rename in renames.items():
    if rename == species_key:
      return name
  return None    
  
def get_reserve_name(key: str) -> str:
  return translate(RESERVE_NAMES[key]["reserve_name"])

def get_reserve(reserve_name: str) -> dict:
  return RESERVES[reserve_name]

def _get_fur(furs: dict, seed: int) -> str:
  try:
    return next(key for key, value in furs.items() if value == seed)
  except:
    return None

def get_animal_fur_by_seed(species: str, gender: str, seed: int) -> str:
  if species not in ANIMALS:
     return "-"

  animal = ANIMALS[species]
  go_furs = animal["go"]["furs"] if "go" in animal and "furs" in animal["go"] else []
  diamond_furs = animal["diamonds"]["furs"] if "furs" in animal["diamonds"] else []
  diamond_furs = diamond_furs[gender] if gender in diamond_furs else []
  go_key = _get_fur(go_furs, seed)
  diamond_key = _get_fur(diamond_furs, seed)
  if go_key:
    return format_key(go_key)
  elif diamond_key:
    return format_key(diamond_key)
  else:
    return "-"

def valid_species_for_reserve(species: str, reserve: str) -> bool:
  return reserve in RESERVES and species in RESERVES[reserve]["species"]

def valid_species(species: str) -> bool:
  return species in list(ANIMALS.keys())

def valid_go_species(species: str) -> bool:
    return species in GreatOnes.__members__

def valid_fur_species(species_key: str) -> bool:
  animal_species = ANIMALS[species_key]["diamonds"]
  gender = animal_species["gender"] if "gender" in animal_species else "male"
  return "furs" in animal_species and gender in animal_species["furs"]

def get_population_file_name(reserve: str):
    index = RESERVES[reserve]["index"]
    return f"animal_population_{index}"
  
def get_population_name(filename: str):
  for _reserve, details in RESERVES.items():
    reserve_filename = f"animal_population_{details['index']}"
    if reserve_filename == filename:
      return details["name"]
  return None