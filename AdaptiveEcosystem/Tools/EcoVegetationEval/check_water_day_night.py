"""Run the catfish day/night food control in a flat, still Python water column."""

from dataclasses import dataclass
from math import isclose


@dataclass
class CatfishPool:
    """Follow a selected submerged patch and debit it at one-second feeding boundaries."""

    patch_x_cm: float = 220.
    stock: float = 10.
    energy: float = 50.
    x_cm: float = 0.
    selected: bool = False
    moving: bool = False

    # Fit only the common speed scale to the Unreal daylight movement sample.
    full_speed_cm_s = 1.198635 / .05 / (.45 + .55 * .26)

    @staticmethod
    def activity(authority_seconds):
        cycle_time = authority_seconds % 120.
        night = cycle_time >= 60.
        phase_time = cycle_time - 60. if night else cycle_time
        edge = min(phase_time, 60. - phase_time)
        darkness = max(0., min(1., .5 + (1. if night else -1.) * edge / 12.))
        return .26 + (.93 - .26) * darkness

    def swim(self, activity, delta_s):
        remaining = self.patch_x_cm - self.x_cm
        self.moving = self.selected and remaining > 5.
        if self.moving:
            speed = self.full_speed_cm_s * (.45 + .55 * activity)
            self.x_cm += min(speed * delta_s, remaining)

    def advance(self, authority_start_s, duration_s):
        for second in range(duration_s + 1):
            now = authority_start_s + second
            activity = self.activity(now)
            distance = abs(self.patch_x_cm - self.x_cm)
            detection_range = 450. * (.25 + .75 * activity)
            self.selected = distance <= detection_range and self.stock >= .2 and self.energy <= 80.
            if second == 0:
                initially_selected = self.selected
            # Match the audit scene: one movement call at start and 20 per elapsed second.
            for frame in range(1 if second == 0 else 20):
                self.swim(self.activity(now if second == 0 else now - 1. + .05 * (frame + 1)), .05)
            if self.selected and not self.moving and self.patch_x_cm - self.x_cm <= 35.:
                amount = min(self.stock, 2., 100. - self.energy)
                if amount >= .2:
                    self.stock -= amount
                    self.energy += amount
                    return initially_selected, second, amount
        return initially_selected, None, 0.


def main():
    move = CatfishPool(selected=True)
    move.swim(move.activity(90.), .05)
    if not isclose(move.x_cm, 1.943486, abs_tol=2e-6):
        raise AssertionError(f"Night step disagrees with the Unreal movement sample: {move.x_cm}")
    for start, expected in ((30, (False, None, 0.)), (90, (True, 6, 2.))):
        world = CatfishPool()
        result = world.advance(start, 7)
        if result != expected or world.stock != 10. - expected[2] or world.energy != 50. + expected[2]:
            raise AssertionError(f"{start}s: expected {expected}, got {result}")
        first_meal = "none" if result[1] is None else f"+{result[1]}s"
        print(f"Start {start}s: selected={result[0]}, first meal={first_meal}, paid={result[2]:g}, stock={world.stock:g}")
    nearby = CatfishPool(patch_x_cm=200.)
    if not nearby.advance(30, 7)[0]:
        raise AssertionError("The closer control should already be detectable during the day")


if __name__ == "__main__":
    main()
