"""Run visual threat and refuge selection in a level model of the Riverbank tunnels."""

from dataclasses import dataclass
from math import cos, dist, hypot, radians, sin

from check_river_rat_refuge import fits_opening, intersects_rectangle, tunnel_coordinates, tunnel_walls


@dataclass(frozen=True)
class Hunter:
    id: int
    position: tuple
    tailing_prey: bool = True
    same_region: bool = True
    alive: bool = True
    can_hunt_rat: bool = True


@dataclass(frozen=True)
class Escape:
    goal: tuple
    site: int | None = None
    via_mouth: bool = False


class RatRefugeWorld:
    """One rat, flat ground, authored boxes and live hunter inputs in cm."""

    def __init__(self, sites, body_scale=1., caution=1., vision=None):
        self.sites = sites
        self.body_scale = body_scale
        self.caution = caution
        self.vision = vision or {
            "eye_height": 5., "night_vision": .8, "threat_sense_range": 650.,
            "threat_sight_half_angle": 90., "threat_near_awareness_range": 280.,
        }
        self.next_sense = 0.
        self.threat_until = 0.
        self.last_threat = None

    def clear_sight(self, start, end, target_height):
        raised_start = (*start[:2], start[2] + self.vision["eye_height"])
        raised_end = (*end[:2], end[2] + target_height)
        for site in self.sites:
            a, b = (tunnel_coordinates(point, site) for point in (raised_start, raised_end))
            opening = site["opening_cm"]
            half_length = opening["length"] / 2.
            half_width = opening["width"] / 2.
            boxes = [(*wall, (0., 100.)) for wall in tunnel_walls(site)]
            boxes.append(((-half_length, half_length), (-half_width, half_width), (opening["height"], 100.)))
            if any(intersects_rectangle(a, b, box) for box in boxes):
                return False
        return True

    def clear_leg(self, start, end):
        for site in self.sites:
            body = site["bodies"]["Rat"]
            radius = min(120., max(1., body["body_radius_cm"] * self.body_scale))
            a, b = (tunnel_coordinates(point, site)[:2] for point in (start, end))
            if any(intersects_rectangle(a, b, wall) for wall in tunnel_walls(site, radius)):
                return False
            opening = site["opening_cm"]
            if not fits_opening(body, self.body_scale, opening) and intersects_rectangle(a, b, (
                (-opening["length"] / 2. - radius, opening["length"] / 2. + radius),
                (-opening["width"] / 2. - radius, opening["width"] / 2. + radius),
            )):
                return False
        return True

    def sense(self, now, position, heading_degrees, darkness, hunters):
        if now < self.next_sense:
            return None
        self.next_sense = now + .45
        best_range = self.vision["threat_sense_range"] * (1. + (self.vision["night_vision"] - 1.) * darkness)
        heading = radians(heading_degrees)
        forward_x, forward_y = cos(heading), sin(heading)
        fov_cos = cos(radians(self.vision["threat_sight_half_angle"]))
        near_awareness = self.vision["threat_near_awareness_range"]
        seen = None
        for hunter in hunters:
            if not (hunter.tailing_prey and hunter.same_region and hunter.alive and hunter.can_hunt_rat):
                continue
            distance = dist(position, hunter.position)
            if distance >= best_range:
                continue
            dx, dy = (b - a for a, b in zip(position[:2], hunter.position[:2]))
            if distance > near_awareness and dx * forward_x + dy * forward_y < hypot(dx, dy) * fov_cos:
                continue
            if self.clear_sight(position, hunter.position, 35.):
                best_range = distance
                seen = hunter
        if seen is not None:
            self.last_threat = seen.position
            self.threat_until = now + 1.5 * self.caution
            return seen.id
        return None

    def choose_refuge(self, position):
        best_length = 650.
        escape = None
        for site in self.sites:
            mouths = [tuple(point) for point in site["mouths_cm"]]
            center = tuple((a + b) / 2. for a, b in zip(*mouths))
            direct_length = dist(position, center)
            if direct_length >= best_length:
                continue
            if self.clear_leg(position, center) and self.clear_sight(position, center, 5.):
                best_length = direct_length
                escape = Escape(center, site["site_index"])
                continue
            for mouth in mouths:
                length = dist(position, mouth) + dist(mouth, center)
                if (length < best_length and self.clear_leg(position, mouth)
                        and self.clear_leg(mouth, center) and self.clear_sight(position, mouth, 5.)):
                    best_length = length
                    escape = Escape(mouth, site["site_index"], True)
        return escape

    def escape(self, now, position):
        if now >= self.threat_until:
            return None
        route = self.choose_refuge(position)
        if route is not None:
            return route
        dx, dy = (a - b for a, b in zip(position[:2], self.last_threat[:2]))
        length = hypot(dx, dy)
        if length == 0.:
            return Escape(tuple(position))
        return Escape((position[0] + dx * 600. / length, position[1] + dy * 600. / length, position[2]))
