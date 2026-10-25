"""Vienotas paroles prasības kontu izveidei un demonstrācijas datiem."""

import unicodedata


def password_errors(password):
    # Unicode kategorijas atpazīst arī latviešu lielos burtus; atstarpe nav speciālais simbols.
    errors = []
    if len(password) < 8:
        errors.append("Parolei jābūt vismaz 8 rakstzīmes garai.")
    if not any(unicodedata.category(char) == "Lu" for char in password):
        errors.append("Parolei jāsatur vismaz 1 lielais burts.")
    if not any(unicodedata.category(char)[0] in {"P", "S"} for char in password):
        errors.append("Parolei jāsatur vismaz 1 speciālais simbols, piemēram, !, @ vai #.")
    return errors
