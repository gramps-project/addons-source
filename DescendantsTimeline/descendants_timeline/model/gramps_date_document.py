from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GrampsDateDocument:
    calendar_code: int
    modifier_code: int
    quality_code: int
    dateval: tuple[int | bool, ...]
    text: str
    newyear: int | tuple[int, ...]
    newyear_was_list: bool

    def __post_init__(self) -> None:
        if type(self.calendar_code) is not int:
            raise TypeError("calendar_code must be an int")
        if type(self.modifier_code) is not int:
            raise TypeError("modifier_code must be an int")
        if type(self.quality_code) is not int:
            raise TypeError("quality_code must be an int")
        if not isinstance(self.dateval, tuple):
            raise TypeError("dateval must be a tuple")
        if not all(isinstance(value, (int, bool)) for value in self.dateval):
            raise TypeError("dateval tuple elements must be int or bool")
        if not isinstance(self.text, str):
            raise TypeError("text must be a str")
        if type(self.newyear) is not int and not isinstance(self.newyear, tuple):
            raise TypeError("newyear must be an int or tuple")
        if isinstance(self.newyear, tuple):
            if not all(type(value) is int for value in self.newyear):
                raise TypeError("newyear tuple elements must be int")
        if type(self.newyear_was_list) is not bool:
            raise TypeError("newyear_was_list must be a bool")
