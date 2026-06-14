from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class LoginForm:
    username: str = ''
    password: str = ''

    @staticmethod
    def from_form(form) -> LoginForm:
        return LoginForm(
            username=form.get('username', '').strip(),
            password=form.get('password', ''),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.username:
            errors.append('Login jest wymagany.')
        if not self.password:
            errors.append('Haslo jest wymagane.')
        return errors


@dataclass(slots=True, frozen=True)
class VehicleForm:
    name: str = ''
    plate: str = ''
    type_: str = ''

    @staticmethod
    def from_form(form) -> VehicleForm:
        return VehicleForm(
            name=form.get('name', '').strip(),
            plate=form.get('plate', '').strip(),
            type_=form.get('type', '').strip(),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.name:
            errors.append('Nazwa pojazdu jest wymagana.')
        return errors


@dataclass(slots=True, frozen=True)
class EquipmentForm:
    vehicle_id: str = ''
    name: str = ''
    category: str = 'Pozostale'
    quantity: int = 1
    unit: str = 'szt'
    notes: str = ''

    @staticmethod
    def from_form(form) -> EquipmentForm:
        try:
            quantity = max(1, int(form.get('quantity', 1)))
        except (ValueError, TypeError):
            quantity = 1
        return EquipmentForm(
            vehicle_id=form.get('vehicle_id', '').strip(),
            name=form.get('name', '').strip(),
            category=form.get('category', 'Pozostale').strip(),
            quantity=quantity,
            unit=form.get('unit', 'szt').strip() or 'szt',
            notes=form.get('notes', '').strip(),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.vehicle_id:
            errors.append('Pojazd jest wymagany.')
        if not self.name:
            errors.append('Nazwa sprzetu jest wymagana.')
        return errors


@dataclass(slots=True, frozen=True)
class UserAddForm:
    username: str = ''
    password: str = ''
    display_name: str = ''
    is_admin: bool = False

    @staticmethod
    def from_form(form) -> UserAddForm:
        return UserAddForm(
            username=form.get('username', '').strip(),
            password=form.get('password', ''),
            display_name=form.get('display_name', '').strip(),
            is_admin=form.get('is_admin') == '1',
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.username:
            errors.append('Login jest wymagany.')
        elif len(self.username) < 3:
            errors.append('Login musi miec co najmniej 3 znaki.')
        if not self.password:
            errors.append('Haslo jest wymagane.')
        elif len(self.password) < 8:
            errors.append('Haslo musi miec co najmniej 8 znakow.')
        if not self.display_name:
            errors.append('Imie i nazwisko jest wymagane.')
        return errors


@dataclass(slots=True, frozen=True)
class UserChangePasswordForm:
    uid: str = ''
    new_password: str = ''

    @staticmethod
    def from_form(form) -> UserChangePasswordForm:
        return UserChangePasswordForm(
            uid=form.get('uid', ''),
            new_password=form.get('new_password', ''),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.uid:
            errors.append('Brak ID uzytkownika.')
        if not self.new_password:
            errors.append('Nowe haslo jest wymagane.')
        elif len(self.new_password) < 8:
            errors.append('Haslo musi miec co najmniej 8 znakow.')
        return errors
