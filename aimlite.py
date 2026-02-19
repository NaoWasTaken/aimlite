import json
import math
import random
from array import array
from dataclasses import dataclass
from pathlib import Path

import pygame


CONFIG_PATH = Path(__file__).with_name("sensitivity_profiles.json")
SCORES_PATH = Path(__file__).with_name("scores.json")


@dataclass
class Crosshair:
    size: int = 12
    thickness: int = 2
    gap: int = 6
    dot: bool = True
    color: tuple[int, int, int] = (0, 255, 180)


@dataclass
class SessionStats:
    score: float = 0.0
    shots: int = 0
    hits: int = 0
    reaction_samples: list[float] | None = None

    def __post_init__(self):
        if self.reaction_samples is None:
            self.reaction_samples = []


class AimLiteApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("AimLite")

        info = pygame.display.Info()
        self.width, self.height = info.current_w, info.current_h
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.FULLSCREEN)
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("consolas", 24)
        self.small_font = pygame.font.SysFont("consolas", 19)
        self.title_font = pygame.font.SysFont("consolas", 44)

        self.running = True
        self.screen_state = "main_menu"

        self.maps = ["regular_flick", "small_flick", "tracking", "reaction"]
        self.map_names = {
            "regular_flick": "Regular Ball Flick",
            "small_flick": "Small Ball Flick",
            "tracking": "Tracking",
            "reaction": "Reaction",
        }
        self.map_index = 0
        self.current_map = self.maps[self.map_index]

        self.durations = [30, 60, 120]
        self.duration_index = 1
        self.selected_duration = self.durations[self.duration_index]

        self._loaded_crosshair_cfg = {}
        self._loaded_audio_cfg = {}
        self.profiles = self._load_profiles()
        self.game_keys = list(self.profiles.keys())
        self.game_index = 0
        self.game_key = self.game_keys[self.game_index]

        self.stats = SessionStats()
        self.crosshair = Crosshair()
        self.sound_enabled = True
        self.master_volume = 0.70
        self.gun_volume = 0.85
        self.hit_volume = 0.65
        self.audio_available = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.ads_held = False

        self.arena_rect = pygame.Rect(0, 0, self.width, self.height)
        self.cursor_x = float(self.arena_rect.centerx)
        self.cursor_y = float(self.arena_rect.centery)

        self.targets: list[dict] = []
        self.moving_target: dict | None = None
        self.reaction_spawn_at = 0.0
        self.reaction_waiting = False

        self.time_left = 0.0
        self.countdown_left = 0.0
        self.score_history: list[dict] = []
        self.high_scores = self._load_scores()
        self.last_run_summary: dict[str, str] = {}
        self.last_run_new_high = False
        self.settings_origin = "main_menu"
        self.recoil_kick = 0.0
        self.muzzle_flash_t = 0.0
        self.muzzle_flash_pos = pygame.Vector2(self.width * 0.5, self.height * 0.5)
        self.muzzle_flash_dir = pygame.Vector2(1.0, 0.0)

        self.click_regions: list[tuple[pygame.Rect, str, str | None]] = []
        self.value_boxes: dict[str, pygame.Rect] = {}
        self.active_input_key: str | None = None
        self.input_buffer = ""
        self.settings_scroll = 0.0

        self.settings_numeric_keys = {
            "hipfire_sens": (0.001, 400.0),
            "ads_sens": (0.01, 200.0),
            "dpi": (50.0, 6400.0),
            "yaw": (0.0001, 1.0),
            "fov_h_deg": (20.0, 179.0),
            "fov_v": (1.0, 179.0),
            "crosshair_size": (2, 50),
            "crosshair_thickness": (1, 8),
            "crosshair_gap": (0, 32),
            "crosshair_red": (0, 255),
            "crosshair_green": (0, 255),
            "crosshair_blue": (0, 255),
            "master_volume": (0.0, 1.0),
            "gun_volume": (0.0, 1.0),
            "hit_volume": (0.0, 1.0),
        }

        self._apply_loaded_settings()
        self._init_audio()
        self._set_input_lock(False)
        self._init_map()

    def _set_input_lock(self, locked: bool):
        pygame.mouse.set_visible(not locked)
        pygame.event.set_grab(locked)
        if locked:
            pygame.mouse.get_rel()

    def _set_state(self, new_state: str):
        self.screen_state = new_state
        self.active_input_key = None
        self.input_buffer = ""
        self.ads_held = False

        if new_state in ("playing", "run_countdown"):
            self._set_input_lock(True)
        else:
            self._set_input_lock(False)

    def _open_settings(self, origin: str):
        self.settings_origin = origin
        self.settings_scroll = 0.0
        self._set_state("settings")

    def _load_profiles(self):
        default_profiles = {
            "cs2": {
                "name": "Counter-Strike 2",
                "yaw": 0.022,
                "hipfire_sens": 1.5,
                "ads_sens": 1.0,
                "dpi": 800,
                "fov_h_deg": 106.26,
            },
            "valorant": {
                "name": "Valorant",
                "yaw": 0.07,
                "hipfire_sens": 0.35,
                "ads_sens": 1.0,
                "dpi": 800,
                "fov_h_deg": 103.0,
            },
            "marvel_rivals": {
                "name": "Marvel Rivals",
                "yaw": 0.0066,
                "hipfire_sens": 2.0,
                "ads_sens": 1.0,
                "dpi": 800,
                "fov_h_deg": 103.0,
            },
            "r6": {
                "name": "Rainbow Six Siege",
                "yaw": 0.0057296,
                "hipfire_sens": 50.0,
                "ads_sens": 50.0,
                "dpi": 800,
                "fov_h_deg": 90.0,
                "x_factor": 0.02,
                "scope_modifier": 0.6,
            },
            "ow2": {
                "name": "Overwatch 2",
                "yaw": 0.0066,
                "hipfire_sens": 4.0,
                "ads_sens": 1.0,
                "dpi": 800,
                "fov_h_deg": 103.0,
            },
        }

        if CONFIG_PATH.exists():
            with CONFIG_PATH.open("r", encoding="utf-8-sig") as f:
                raw = json.load(f)

            profiles_in = raw.get("profiles") if isinstance(raw, dict) and "profiles" in raw else raw
            if isinstance(raw, dict):
                self._loaded_crosshair_cfg = raw.get("crosshair", {}) or {}
                self._loaded_audio_cfg = raw.get("audio", {}) or {}

            merged = {k: dict(v) for k, v in default_profiles.items()}
            if isinstance(profiles_in, dict):
                for game_key, base in merged.items():
                    custom = profiles_in.get(game_key)
                    if isinstance(custom, dict):
                        base.update(custom)
            return merged

        return default_profiles

    def _save_profiles(self):
        payload = {
            "profiles": self.profiles,
            "crosshair": {
                "size": self.crosshair.size,
                "thickness": self.crosshair.thickness,
                "gap": self.crosshair.gap,
                "dot": self.crosshair.dot,
                "color": [self.crosshair.color[0], self.crosshair.color[1], self.crosshair.color[2]],
            },
            "audio": {
                "enabled": self.sound_enabled,
                "master_volume": self.master_volume,
                "gun_volume": self.gun_volume,
                "hit_volume": self.hit_volume,
            },
        }
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def _default_high_scores(self):
        return {
            "regular_flick": {"score": 0.0, "shots": 0, "hits": 0, "acc": 0.0, "game": "-", "duration": 0},
            "small_flick": {"score": 0.0, "shots": 0, "hits": 0, "acc": 0.0, "game": "-", "duration": 0},
            "tracking": {"score": 0.0, "shots": 0, "hits": 0, "acc": 0.0, "game": "-", "duration": 0},
            "reaction": {"score": 0.0, "shots": 0, "hits": 0, "acc": 0.0, "game": "-", "duration": 0},
        }

    def _load_scores(self):
        # Store only per-map high scores for long-term progression.
        default = self._default_high_scores()
        if SCORES_PATH.exists():
            try:
                with SCORES_PATH.open("r", encoding="utf-8-sig") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    for k in default.keys():
                        if isinstance(raw.get(k), dict):
                            default[k].update(raw[k])
            except (OSError, json.JSONDecodeError):
                pass
        return default

    def _save_scores(self):
        with SCORES_PATH.open("w", encoding="utf-8") as f:
            json.dump(self.high_scores, f, indent=2)

    def _apply_loaded_settings(self):
        c = self._loaded_crosshair_cfg
        if isinstance(c, dict):
            self.crosshair.size = int(max(2, min(50, c.get("size", self.crosshair.size))))
            self.crosshair.thickness = int(max(1, min(8, c.get("thickness", self.crosshair.thickness))))
            self.crosshair.gap = int(max(0, min(32, c.get("gap", self.crosshair.gap))))
            self.crosshair.dot = bool(c.get("dot", self.crosshair.dot))
            color = c.get("color", list(self.crosshair.color))
            if isinstance(color, (list, tuple)) and len(color) == 3:
                self.crosshair.color = (
                    int(max(0, min(255, color[0]))),
                    int(max(0, min(255, color[1]))),
                    int(max(0, min(255, color[2]))),
                )

        a = self._loaded_audio_cfg
        if isinstance(a, dict):
            self.sound_enabled = bool(a.get("enabled", self.sound_enabled))
            self.master_volume = float(max(0.0, min(1.0, a.get("master_volume", self.master_volume))))
            self.gun_volume = float(max(0.0, min(1.0, a.get("gun_volume", self.gun_volume))))
            self.hit_volume = float(max(0.0, min(1.0, a.get("hit_volume", self.hit_volume))))

    def _build_sound(self, duration_sec, sample_fn, sample_rate=44100):
        samples = int(duration_sec * sample_rate)
        data = array("h")
        for i in range(samples):
            t = i / sample_rate
            v = max(-1.0, min(1.0, sample_fn(t)))
            data.append(int(v * 32767))
        return pygame.mixer.Sound(buffer=data.tobytes())

    def _init_audio(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=1)
            self.audio_available = True

            def gun_fn(t):
                env = math.exp(-t * 14.0)
                crack = (random.random() * 2.0 - 1.0) * math.exp(-t * 52.0)
                mid = math.sin(2.0 * math.pi * (280.0 - 140.0 * t) * t) * math.exp(-t * 20.0)
                bass = math.sin(2.0 * math.pi * 95.0 * t) * math.exp(-t * 10.0)
                return (0.55 * crack + 0.50 * mid + 0.30 * bass) * env

            def hit_fn(t):
                tone = math.sin(2.0 * math.pi * 940.0 * t) * math.exp(-t * 30.0)
                return tone * 0.45

            self.sounds["gun"] = self._build_sound(0.18, gun_fn)
            self.sounds["hit"] = self._build_sound(0.09, hit_fn)
            self._apply_sound_volumes()
        except pygame.error:
            self.audio_available = False
            self.sounds = {}

    def _apply_sound_volumes(self):
        if not self.audio_available:
            return
        if "gun" in self.sounds:
            self.sounds["gun"].set_volume(self.master_volume * self.gun_volume)
        if "hit" in self.sounds:
            self.sounds["hit"].set_volume(self.master_volume * self.hit_volume)

    def _play_sound(self, key: str):
        if not self.sound_enabled or not self.audio_available:
            return
        snd = self.sounds.get(key)
        if snd:
            snd.play()

    def _profile(self):
        return self.profiles[self.game_key]

    def _fov_h_to_v(self, h_deg, aspect):
        h = math.radians(h_deg)
        v = 2.0 * math.atan(math.tan(h / 2.0) / aspect)
        return math.degrees(v)

    def _fov_v_to_h(self, v_deg, aspect):
        v = math.radians(v_deg)
        h = 2.0 * math.atan(math.tan(v / 2.0) * aspect)
        return math.degrees(h)

    def _active_sens(self):
        p = self._profile()
        hip = max(1e-6, float(p["hipfire_sens"]))

        if self.game_key == "r6" and self.ads_held:
            ads = float(p.get("ads_sens", 50.0))
            x_factor = float(p.get("x_factor", 0.02))
            scope_mod = float(p.get("scope_modifier", 0.6))
            ads_modifier = max(0.0, min(1.0, (ads * x_factor) * scope_mod))
            return hip * ads_modifier

        if self.ads_held:
            return hip * max(0.01, float(p.get("ads_sens", 1.0)))

        return hip

    def _cm360(self):
        p = self._profile()
        dpi = max(1e-6, float(p["dpi"]))
        yaw = max(1e-6, float(p["yaw"]))
        sens = self._active_sens()
        return (360.0 * 2.54) / (dpi * yaw * sens)

    def _spawn_cluster_point(self, cluster_scale=0.28):
        center_x, center_y = self.arena_rect.center
        radius = min(self.arena_rect.w, self.arena_rect.h) * cluster_scale
        angle = random.random() * math.tau
        dist = (random.random() ** 0.5) * radius
        x = center_x + math.cos(angle) * dist
        y = center_y + math.sin(angle) * dist
        x = max(self.arena_rect.left + 36, min(self.arena_rect.right - 36, x))
        y = max(self.arena_rect.top + 36, min(self.arena_rect.bottom - 36, y))
        return x, y

    def _spawn_target(self, r, cluster_scale=0.28):
        x, y = self._spawn_cluster_point(cluster_scale)
        return {"x": x, "y": y, "r": r}

    def _spawn_non_overlapping_target(self, existing_targets, radius, cluster_scale=0.28, min_gap=12.0):
        for _ in range(60):
            candidate = self._spawn_target(radius, cluster_scale)
            collides = False
            for other in existing_targets:
                dx = candidate["x"] - other["x"]
                dy = candidate["y"] - other["y"]
                min_dist = candidate["r"] + other["r"] + min_gap
                if dx * dx + dy * dy < min_dist * min_dist:
                    collides = True
                    break
            if not collides:
                return candidate
        return self._spawn_target(radius, cluster_scale)

    def _init_map(self):
        self.targets.clear()
        self.moving_target = None
        now = pygame.time.get_ticks() / 1000.0
        self.recoil_kick = 0.0
        self.muzzle_flash_t = 0.0
        self.muzzle_flash_pos = pygame.Vector2(self.width * 0.5, self.height * 0.5)
        self.muzzle_flash_dir = pygame.Vector2(1.0, 0.0)

        if self.current_map == "regular_flick":
            for _ in range(3):
                self.targets.append(self._spawn_non_overlapping_target(self.targets, 30, cluster_scale=0.10))
        elif self.current_map == "small_flick":
            for _ in range(3):
                self.targets.append(self._spawn_non_overlapping_target(self.targets, 16, cluster_scale=0.24))
        elif self.current_map == "reaction":
            self.targets = []
            self.reaction_waiting = True
            self.reaction_spawn_at = now + random.uniform(0.5, 1.5)
        elif self.current_map == "tracking":
            speed = 210 * (1.0 + (self.game_index * 0.05))
            base_h = 126
            base_w = 42
            self.moving_target = {
                "x": float(self.arena_rect.centerx),
                "y": float(self.arena_rect.centery),
                "ground_y": float(self.arena_rect.centery),
                "w": base_w,
                "h": base_h,
                "base_w": base_w,
                "base_h": base_h,
                "vx": random.choice([-1.0, 1.0]) * speed * 0.7,
                "jump_v": 0.0,
                "jumping": False,
                "strafe_timer": random.uniform(0.22, 0.55),
                "crouch_timer": 0.0,
                "crouch_cooldown": random.uniform(1.6, 3.2),
                "jump_cooldown": random.uniform(2.0, 4.0),
            }

    def _px_per_degree(self):
        h_fov = max(1e-3, float(self._profile().get("fov_h_deg", 103.0)))
        return self.arena_rect.w / h_fov

    def _fire_shot_point(self):
        # Stronger one-tap kick closer to a Deagle feel.
        self.recoil_kick = min(1.8, self.recoil_kick + 0.55)
        self.muzzle_flash_t = 0.06
        return self.cursor_x, self.cursor_y

    def _update_weapon(self, dt):
        # Slightly slower recovery so recoil reads clearly.
        self.recoil_kick = max(0.0, self.recoil_kick - (2.9 * dt))
        self.muzzle_flash_t = max(0.0, self.muzzle_flash_t - dt)

    def _switch_map(self, delta):
        self.map_index = (self.map_index + delta) % len(self.maps)
        self.current_map = self.maps[self.map_index]
        self._init_map()

    def _switch_game(self, delta):
        self.game_index = (self.game_index + delta) % len(self.game_keys)
        self.game_key = self.game_keys[self.game_index]

    def _register_shot(self):
        self.stats.shots += 1

    def _register_hit(self, value=10.0):
        self.stats.hits += 1
        self.stats.score += value

    def _is_in_circle(self, x, y, t):
        dx, dy = x - t["x"], y - t["y"]
        return dx * dx + dy * dy <= t["r"] * t["r"]

    def _is_in_rect(self, x, y, t):
        left = t["x"] - t["w"] / 2
        top = t["y"] - t["h"] / 2
        return left <= x <= left + t["w"] and top <= y <= top + t["h"]

    def _handle_training_click(self):
        self._register_shot()
        self._play_sound("gun")
        shot_x, shot_y = self._fire_shot_point()
        hit = False

        if self.current_map in ("regular_flick", "small_flick"):
            radius = 30 if self.current_map == "regular_flick" else 16
            for i, t in enumerate(self.targets):
                if self._is_in_circle(shot_x, shot_y, t):
                    others = [x for idx, x in enumerate(self.targets) if idx != i]
                    self.targets[i] = self._spawn_non_overlapping_target(others, radius, cluster_scale=0.24)
                    self._register_hit(10.0)
                    hit = True
                    break

        elif self.current_map == "reaction" and self.targets:
            t = self.targets[0]
            if self._is_in_circle(shot_x, shot_y, t):
                now = pygame.time.get_ticks() / 1000.0
                self.stats.reaction_samples.append((now - self.reaction_spawn_at) * 1000.0)
                self.targets = []
                self.reaction_waiting = True
                self.reaction_spawn_at = now + random.uniform(0.5, 1.5)
                self._register_hit(15.0)
                hit = True

        elif self.current_map == "tracking" and self.moving_target:
            if self._is_in_rect(shot_x, shot_y, self.moving_target):
                self._register_hit(5.0)
                hit = True

        if not hit:
            self.stats.score = max(0.0, self.stats.score - 2.0)
        else:
            self._play_sound("hit")

    def _draw_crosshair(self):
        x, y = int(self.cursor_x), int(self.cursor_y)
        c = self.crosshair.color
        t = self.crosshair.thickness
        g = self.crosshair.gap
        s = self.crosshair.size

        pygame.draw.line(self.screen, c, (x - g - s, y), (x - g, y), t)
        pygame.draw.line(self.screen, c, (x + g, y), (x + g + s, y), t)
        pygame.draw.line(self.screen, c, (x, y - g - s), (x, y - g), t)
        pygame.draw.line(self.screen, c, (x, y + g), (x, y + g + s), t)

        if self.crosshair.dot:
            pygame.draw.circle(self.screen, c, (x, y), max(1, t))

    def _draw_target_circle(self, t, color=(255, 108, 96)):
        center = (int(t["x"]), int(t["y"]))
        pygame.draw.circle(self.screen, color, center, int(t["r"]))
        pygame.draw.circle(self.screen, (245, 248, 255), center, int(t["r"]), 2)

    def _draw_weapon(self):
        # Perspective-style first-person viewmodel: points toward the target.
        hand = pygame.Vector2(self.width * 0.80, self.height * 0.87)
        aim = pygame.Vector2(self.cursor_x, self.cursor_y)
        forward = aim - hand
        if forward.length_squared() < 1.0:
            forward = pygame.Vector2(-1.0, -0.2)
        else:
            forward = forward.normalize()

        right = pygame.Vector2(-forward.y, forward.x)
        down = pygame.Vector2(0.0, 1.0)

        recoil_back = forward * (self.recoil_kick * 70.0)
        recoil_up = down * (-self.recoil_kick * 26.0)
        pivot = hand - recoil_back + recoil_up

        def pt(base: pygame.Vector2, f=0.0, r=0.0, d=0.0):
            p = base + (forward * f) + (right * r) + (down * d)
            return (int(p.x), int(p.y))

        rear = pivot + forward * 8.0
        front = rear + forward * 330.0

        # Foreshortened slide/body toward muzzle (front-to-back feel).
        rear_w = 108.0
        front_w = 44.0
        rear_t = 34.0
        front_t = 18.0

        top_face = [
            pt(rear, r=rear_w * 0.5),
            pt(rear, r=-rear_w * 0.5),
            pt(front, r=-front_w * 0.5),
            pt(front, r=front_w * 0.5),
        ]
        right_face = [
            pt(rear, r=-rear_w * 0.5),
            pt(front, r=-front_w * 0.5),
            pt(front, r=-front_w * 0.5, d=front_t),
            pt(rear, r=-rear_w * 0.5, d=rear_t),
        ]
        left_face = [
            pt(rear, r=rear_w * 0.5),
            pt(front, r=front_w * 0.5),
            pt(front, r=front_w * 0.5, d=front_t),
            pt(rear, r=rear_w * 0.5, d=rear_t),
        ]

        # Lower frame chunk.
        frame_rear = rear - forward * 18.0
        frame_front = front - forward * 38.0
        frame_top = [
            pt(frame_rear, r=rear_w * 0.38, d=rear_t * 0.7),
            pt(frame_rear, r=-rear_w * 0.38, d=rear_t * 0.7),
            pt(frame_front, r=-front_w * 0.62, d=front_t * 1.2),
            pt(frame_front, r=front_w * 0.62, d=front_t * 1.2),
        ]

        # Grip attached near hand (screen-down).
        grip = [
            pt(rear, f=-36, r=26, d=12),
            pt(rear, f=-34, r=-16, d=12),
            pt(rear, f=-20, r=-14, d=186),
            pt(rear, f=-8, r=18, d=206),
            pt(rear, f=-16, r=38, d=140),
        ]

        pygame.draw.polygon(self.screen, (82, 91, 106), right_face)
        pygame.draw.polygon(self.screen, (97, 108, 124), left_face)
        pygame.draw.polygon(self.screen, (114, 126, 144), top_face)
        pygame.draw.polygon(self.screen, (66, 74, 89), frame_top)
        pygame.draw.polygon(self.screen, (70, 78, 94), grip)

        pygame.draw.polygon(self.screen, (138, 154, 176), top_face, 2)
        pygame.draw.polygon(self.screen, (112, 125, 145), grip, 2)

        # Muzzle opening.
        muzzle_center = pygame.Vector2(pt(front, d=front_t * 0.55))
        self.muzzle_flash_pos = muzzle_center
        self.muzzle_flash_dir = forward
        pygame.draw.circle(self.screen, (26, 30, 38), (int(muzzle_center.x), int(muzzle_center.y)), 10)
        pygame.draw.circle(self.screen, (104, 115, 130), (int(muzzle_center.x), int(muzzle_center.y)), 10, 2)

    def _draw_muzzle_flash(self):
        if self.muzzle_flash_t <= 0.0:
            return

        intensity = min(1.0, self.muzzle_flash_t / 0.06)
        p = self.muzzle_flash_pos
        fwd = self.muzzle_flash_dir
        right = pygame.Vector2(-fwd.y, fwd.x)
        length = 88.0 * intensity
        width = 34.0 * intensity

        flash_poly = [
            (int(p.x + fwd.x * 8 + right.x * (width * 0.5)), int(p.y + fwd.y * 8 + right.y * (width * 0.5))),
            (int(p.x + fwd.x * length), int(p.y + fwd.y * length)),
            (int(p.x + fwd.x * 8 - right.x * (width * 0.5)), int(p.y + fwd.y * 8 - right.y * (width * 0.5))),
        ]
        pygame.draw.polygon(self.screen, (255, 226, 148), flash_poly)
        pygame.draw.circle(self.screen, (255, 243, 188), (int(p.x), int(p.y)), int(16 * intensity))

    def _draw_tracking_target(self):
        t = self.moving_target
        if not t:
            return

        rect = pygame.Rect(
            int(t["x"] - t["w"] / 2),
            int(t["y"] - t["h"] / 2),
            int(t["w"]),
            int(t["h"]),
        )
        pygame.draw.rect(self.screen, (93, 197, 255), rect, border_radius=12)

    def _draw_button(self, rect: pygame.Rect, text: str, active=False):
        bg = (31, 50, 70) if active else (21, 33, 47)
        border = (102, 171, 230) if active else (62, 90, 120)
        pygame.draw.rect(self.screen, bg, rect, border_radius=10)
        pygame.draw.rect(self.screen, border, rect, 2, border_radius=10)
        surf = self.font.render(text, True, (230, 238, 248))
        self.screen.blit(surf, (rect.centerx - surf.get_width() // 2, rect.centery - surf.get_height() // 2))

    def _draw_main_menu(self):
        self.click_regions.clear()
        self.screen.fill((9, 14, 22))

        title = self.title_font.render("AimLite", True, (236, 245, 255))
        self.screen.blit(title, (self.width // 2 - title.get_width() // 2, 100))

        options = [
            ("Play", "main_play"),
            ("Select Map", "main_map"),
            ("Settings", "main_settings"),
            ("Scores", "main_scores"),
            ("Quit", "main_quit"),
        ]

        w, h = 360, 64
        x = self.width // 2 - w // 2
        y = 230
        gap = 18
        for label, action in options:
            rect = pygame.Rect(x, y, w, h)
            self._draw_button(rect, label)
            self.click_regions.append((rect, action, None))
            y += h + gap

    def _draw_map_select(self):
        self.click_regions.clear()
        self.screen.fill((9, 14, 22))

        title = self.title_font.render("Select Map", True, (236, 245, 255))
        self.screen.blit(title, (80, 60))

        y = 150
        for i, map_key in enumerate(self.maps):
            rect = pygame.Rect(80, y, 520, 60)
            self._draw_button(rect, self.map_names[map_key], active=(i == self.map_index))
            self.click_regions.append((rect, "map_pick", map_key))
            y += 74

        dur_title = self.font.render("Time Limit", True, (236, 245, 255))
        self.screen.blit(dur_title, (700, 160))

        for i, dur in enumerate(self.durations):
            rect = pygame.Rect(700, 210 + i * 74, 260, 60)
            self._draw_button(rect, f"{dur} sec", active=(i == self.duration_index))
            self.click_regions.append((rect, "duration_pick", str(i)))

        start_rect = pygame.Rect(700, 470, 260, 64)
        back_rect = pygame.Rect(700, 548, 260, 64)
        self._draw_button(start_rect, "Start")
        self._draw_button(back_rect, "Back")
        self.click_regions.append((start_rect, "start_run", None))
        self.click_regions.append((back_rect, "back_main", None))

    def _draw_scores(self):
        self.click_regions.clear()
        self.screen.fill((9, 14, 22))

        title = self.title_font.render("Scores", True, (236, 245, 255))
        self.screen.blit(title, (80, 60))

        header = self.small_font.render("Per-Map High Scores (saved locally)", True, (167, 206, 241))
        self.screen.blit(header, (80, 130))

        y = 170
        for map_key in self.maps:
            hs = self.high_scores.get(map_key, {})
            txt = (
                f"{self.map_names[map_key]} | Score {float(hs.get('score', 0.0)):.0f} | "
                f"Acc {float(hs.get('acc', 0.0)):.1f}% | Hits {int(hs.get('hits', 0))}/{int(hs.get('shots', 0))} | "
                f"{hs.get('game', '-')} @ {int(hs.get('duration', 0))}s"
            )
            surf = self.small_font.render(txt, True, (224, 235, 245))
            self.screen.blit(surf, (80, y))
            y += 36

        back_rect = pygame.Rect(80, self.height - 100, 220, 60)
        clear_rect = pygame.Rect(320, self.height - 100, 220, 60)
        self._draw_button(back_rect, "Back")
        self._draw_button(clear_rect, "Clear")
        self.click_regions.append((back_rect, "back_main", None))
        self.click_regions.append((clear_rect, "scores_clear", None))

    def _format_setting_value(self, key: str):
        p = self._profile()
        aspect = self.width / self.height

        if key == "game_name":
            return p["name"]
        if key == "hipfire_sens":
            return f"{p['hipfire_sens']:.3f}"
        if key == "ads_sens":
            return f"{p['ads_sens']:.3f}"
        if key == "dpi":
            return f"{p['dpi']:.0f}"
        if key == "yaw":
            return f"{p['yaw']:.6f}"
        if key == "cm360":
            return f"{self._cm360():.2f}"
        if key == "fov_h_deg":
            return f"{p['fov_h_deg']:.2f}"
        if key == "fov_v":
            return f"{self._fov_h_to_v(float(p['fov_h_deg']), aspect):.2f}"
        if key == "crosshair_size":
            return str(self.crosshair.size)
        if key == "crosshair_thickness":
            return str(self.crosshair.thickness)
        if key == "crosshair_gap":
            return str(self.crosshair.gap)
        if key == "crosshair_red":
            return str(self.crosshair.color[0])
        if key == "crosshair_green":
            return str(self.crosshair.color[1])
        if key == "crosshair_blue":
            return str(self.crosshair.color[2])
        if key == "crosshair_dot":
            return "On" if self.crosshair.dot else "Off"
        if key == "sound_enabled":
            return "On" if self.sound_enabled else "Off"
        if key == "master_volume":
            return f"{self.master_volume:.2f}"
        if key == "gun_volume":
            return f"{self.gun_volume:.2f}"
        if key == "hit_volume":
            return f"{self.hit_volume:.2f}"
        return ""

    def _draw_settings(self):
        self.click_regions.clear()
        self.value_boxes.clear()

        self.screen.fill((9, 14, 22))
        title = self.title_font.render("Settings", True, (236, 245, 255))
        self.screen.blit(title, (80, 40))

        left_x = 80
        value_x = 460
        btn_x = 660
        content_top = 120
        content_bottom = self.height - 170
        row_h = 36
        row_step = 34
        y = 130 - self.settings_scroll

        rows = [
            ("Game Profile", "game_name", False),
            ("Hipfire Sens", "hipfire_sens", True),
            ("ADS Setting", "ads_sens", True),
            ("Mouse DPI", "dpi", True),
            ("Yaw Coefficient", "yaw", True),
            ("cm/360", "cm360", False),
            ("Horizontal FOV", "fov_h_deg", True),
            ("Vertical FOV", "fov_v", True),
            ("Crosshair Size", "crosshair_size", True),
            ("Crosshair Thickness", "crosshair_thickness", True),
            ("Crosshair Gap", "crosshair_gap", True),
            ("Crosshair Red", "crosshair_red", True),
            ("Crosshair Green", "crosshair_green", True),
            ("Crosshair Blue", "crosshair_blue", True),
            ("Crosshair Dot", "crosshair_dot", False),
            ("Sound Enabled", "sound_enabled", False),
            ("Master Volume", "master_volume", True),
            ("Gun Volume", "gun_volume", True),
            ("Hit Volume", "hit_volume", True),
        ]

        content_height = len(rows) * row_step
        view_height = max(1, content_bottom - 130)
        max_scroll = max(0.0, content_height - view_height)
        self.settings_scroll = max(0.0, min(self.settings_scroll, max_scroll))

        for label, key, editable in rows:
            visible = (y + row_h >= content_top) and (y <= content_bottom)
            if visible:
                label_surf = self.small_font.render(label, True, (226, 236, 245))
                self.screen.blit(label_surf, (left_x, y + 8))

                value_rect = pygame.Rect(value_x, int(y), 180, row_h)
                active = self.active_input_key == key
                bg = (38, 58, 84) if active else (21, 33, 47)
                border = (114, 194, 255) if active else (62, 90, 120)
                pygame.draw.rect(self.screen, bg, value_rect, border_radius=8)
                pygame.draw.rect(self.screen, border, value_rect, 2, border_radius=8)

                if active:
                    text = self.input_buffer
                else:
                    text = self._format_setting_value(key)

                val_surf = self.small_font.render(text, True, (232, 240, 250))
                self.screen.blit(val_surf, (value_rect.x + 10, value_rect.y + 7))

                if editable:
                    self.click_regions.append((value_rect, "settings_edit", key))
                    self.value_boxes[key] = value_rect

                if key == "game_name":
                    prev_rect = pygame.Rect(btn_x, int(y), 44, row_h)
                    next_rect = pygame.Rect(btn_x + 54, int(y), 44, row_h)
                    self._draw_button(prev_rect, "<")
                    self._draw_button(next_rect, ">")
                    self.click_regions.append((prev_rect, "game_cycle", "-1"))
                    self.click_regions.append((next_rect, "game_cycle", "1"))

                if key == "crosshair_dot":
                    toggle_rect = pygame.Rect(btn_x, int(y), 98, row_h)
                    self._draw_button(toggle_rect, "Toggle")
                    self.click_regions.append((toggle_rect, "dot_toggle", None))

                if key == "sound_enabled":
                    toggle_rect = pygame.Rect(btn_x, int(y), 98, row_h)
                    self._draw_button(toggle_rect, "Toggle")
                    self.click_regions.append((toggle_rect, "sound_toggle", None))

            y += row_step

        if max_scroll > 0:
            bar_rect = pygame.Rect(self.width - 34, content_top, 10, content_bottom - content_top)
            pygame.draw.rect(self.screen, (35, 50, 68), bar_rect, border_radius=5)
            knob_h = max(34, int(bar_rect.h * (view_height / max(content_height, 1))))
            knob_y = int(bar_rect.y + (self.settings_scroll / max_scroll) * (bar_rect.h - knob_h))
            knob = pygame.Rect(bar_rect.x, knob_y, bar_rect.w, knob_h)
            pygame.draw.rect(self.screen, (96, 156, 210), knob, border_radius=5)

        hint = self.small_font.render("Click a value box, type exact number, press Enter to apply.", True, (157, 212, 255))
        self.screen.blit(hint, (80, self.height - 150))

        save_rect = pygame.Rect(80, self.height - 100, 220, 60)
        back_rect = pygame.Rect(320, self.height - 100, 220, 60)
        back_label = "Resume" if self.settings_origin == "playing" else "Back"
        self._draw_button(save_rect, "Save Profiles")
        self._draw_button(back_rect, back_label)
        self.click_regions.append((save_rect, "settings_save", None))
        self.click_regions.append((back_rect, "settings_back", None))

    def _draw_run_summary(self):
        self.click_regions.clear()
        self.screen.fill((9, 14, 22))

        title = self.title_font.render("Run Summary", True, (236, 245, 255))
        self.screen.blit(title, (80, 70))

        sub = "NEW HIGH SCORE" if self.last_run_new_high else "Run Complete"
        sub_surf = self.font.render(sub, True, (158, 235, 177) if self.last_run_new_high else (184, 204, 224))
        self.screen.blit(sub_surf, (80, 130))

        y = 190
        rows = [
            f"Map: {self.last_run_summary.get('map', '-')}",
            f"Game: {self.last_run_summary.get('game', '-')}",
            f"Time: {self.last_run_summary.get('duration', '-')}",
            f"Shots Fired: {self.last_run_summary.get('shots', '0')}",
            f"Targets Killed: {self.last_run_summary.get('hits', '0')}",
            f"Accuracy: {self.last_run_summary.get('acc', '0.0%')}",
            f"Score: {self.last_run_summary.get('score', '0')}",
        ]
        for r in rows:
            surf = self.font.render(r, True, (224, 235, 245))
            self.screen.blit(surf, (80, y))
            y += 44

        play_again = pygame.Rect(80, self.height - 110, 220, 64)
        view_scores = pygame.Rect(320, self.height - 110, 220, 64)
        menu = pygame.Rect(560, self.height - 110, 220, 64)
        self._draw_button(play_again, "Play Again")
        self._draw_button(view_scores, "Scores")
        self._draw_button(menu, "Main Menu")
        self.click_regions.append((play_again, "summary_play_again", None))
        self.click_regions.append((view_scores, "summary_scores", None))
        self.click_regions.append((menu, "summary_menu", None))

    def _draw_countdown(self):
        self.screen.fill((7, 12, 18))
        title = self.title_font.render(self.map_names[self.current_map], True, (236, 245, 255))
        self.screen.blit(title, (self.width // 2 - title.get_width() // 2, self.height // 2 - 130))
        sec = max(1, int(math.ceil(self.countdown_left)))
        num = self.title_font.render(str(sec), True, (158, 235, 177))
        self.screen.blit(num, (self.width // 2 - num.get_width() // 2, self.height // 2 - 40))
        sub = self.font.render("Get ready...", True, (184, 204, 224))
        self.screen.blit(sub, (self.width // 2 - sub.get_width() // 2, self.height // 2 + 28))

    def _draw_training(self):
        self.screen.fill((7, 12, 18))

        if self.current_map == "tracking":
            self._draw_tracking_target()
        else:
            for t in self.targets:
                self._draw_target_circle(t)

        self._draw_weapon()
        self._draw_muzzle_flash()
        self._draw_crosshair()

        acc = 0.0 if self.stats.shots == 0 else (self.stats.hits / self.stats.shots) * 100.0
        hud = [
            f"{self._profile()['name']} | {self.map_names[self.current_map]} | {self.time_left:05.1f}s",
            f"Score {self.stats.score:.0f}  Hits {self.stats.hits}/{self.stats.shots} ({acc:.1f}%)",
            "Esc: Settings",
        ]

        y = 16
        for line in hud:
            surf = self.small_font.render(line, True, (220, 232, 245))
            shadow = self.small_font.render(line, True, (8, 10, 14))
            self.screen.blit(shadow, (18 + 1, y + 1))
            self.screen.blit(surf, (18, y))
            y += 24

        if self.current_map == "reaction" and self.reaction_waiting:
            txt = self.font.render("Get Ready...", True, (168, 213, 255))
            self.screen.blit(txt, (self.width // 2 - txt.get_width() // 2, self.height // 2 - 140))

    def _update_tracking(self, dt):
        t = self.moving_target
        if not t:
            return

        speed = 210 * (1.0 + (self.game_index * 0.05))
        t["strafe_timer"] -= dt
        t["crouch_cooldown"] -= dt
        t["jump_cooldown"] -= dt

        # Unpredictable horizontal strafing with frequent velocity changes.
        if t["strafe_timer"] <= 0.0:
            mag = random.uniform(0.45, 1.0) * speed
            t["vx"] = random.choice([-1.0, 1.0]) * mag
            t["strafe_timer"] = random.uniform(0.16, 0.48)

        t["x"] += t["vx"] * dt

        # Occasional crouch (half height), only when grounded.
        if not t["jumping"] and t["crouch_timer"] <= 0.0 and t["crouch_cooldown"] <= 0.0:
            if random.random() < 0.38:
                t["crouch_timer"] = random.uniform(0.30, 0.85)
            t["crouch_cooldown"] = random.uniform(1.5, 3.8)

        if t["crouch_timer"] > 0.0:
            t["crouch_timer"] -= dt
            t["h"] = t["base_h"] * 0.5
        else:
            t["h"] = t["base_h"]

        # Occasional jump event, little to no normal vertical drift.
        if not t["jumping"] and t["jump_cooldown"] <= 0.0:
            if random.random() < 0.24:
                t["jumping"] = True
                t["jump_v"] = -430.0
            t["jump_cooldown"] = random.uniform(2.2, 4.6)

        if t["jumping"]:
            t["jump_v"] += 1000.0 * dt
            t["y"] += t["jump_v"] * dt
            if t["y"] >= t["ground_y"]:
                t["y"] = t["ground_y"]
                t["jump_v"] = 0.0
                t["jumping"] = False
        else:
            # Keep bottom anchored while crouching.
            if t["h"] < t["base_h"]:
                t["y"] = t["ground_y"] + (t["base_h"] * 0.25)
            else:
                t["y"] = t["ground_y"]

        half_w, half_h = t["w"] / 2, t["h"] / 2

        if t["x"] - half_w < self.arena_rect.left:
            t["x"] = self.arena_rect.left + half_w
            t["vx"] = abs(t["vx"])
        elif t["x"] + half_w > self.arena_rect.right:
            t["x"] = self.arena_rect.right - half_w
            t["vx"] = -abs(t["vx"])
            t["x"] = max(self.arena_rect.left + half_w, min(self.arena_rect.right - half_w, t["x"]))

        if self._is_in_rect(self.cursor_x, self.cursor_y, t):
            self.stats.score += 6.0 * dt

    def _update_mouse(self):
        rel_x, rel_y = pygame.mouse.get_rel()
        p = self._profile()

        yaw = max(1e-6, float(p["yaw"]))
        sens = self._active_sens()
        px_per_degree = self._px_per_degree()
        px_per_count = yaw * sens * px_per_degree

        self.cursor_x += rel_x * px_per_count
        self.cursor_y += rel_y * px_per_count

        self.cursor_x = max(self.arena_rect.left, min(self.arena_rect.right, self.cursor_x))
        self.cursor_y = max(self.arena_rect.top, min(self.arena_rect.bottom, self.cursor_y))

    def _start_run(self):
        self.stats = SessionStats()
        self.selected_duration = self.durations[self.duration_index]
        self.time_left = float(self.selected_duration)
        self.countdown_left = 3.0
        self._init_map()
        self._set_state("run_countdown")

    def _finish_run(self):
        acc = 0.0 if self.stats.shots == 0 else (self.stats.hits / self.stats.shots) * 100.0
        if self.stats.reaction_samples:
            avg_reaction = f"{sum(self.stats.reaction_samples) / len(self.stats.reaction_samples):.1f} ms"
        else:
            avg_reaction = "-"

        self.score_history.append(
            {
                "map": self.map_names[self.current_map],
                "game": self._profile()["name"],
                "duration": self.selected_duration,
                "score": self.stats.score,
                "acc": acc,
                "reaction": avg_reaction,
            }
        )

        hs = self.high_scores[self.current_map]
        self.last_run_new_high = self.stats.score > float(hs.get("score", 0.0))
        if self.last_run_new_high:
            self.high_scores[self.current_map] = {
                "score": float(self.stats.score),
                "shots": int(self.stats.shots),
                "hits": int(self.stats.hits),
                "acc": float(acc),
                "game": self._profile()["name"],
                "duration": int(self.selected_duration),
            }
            self._save_scores()

        self.last_run_summary = {
            "map": self.map_names[self.current_map],
            "game": self._profile()["name"],
            "duration": f"{self.selected_duration}s",
            "shots": str(self.stats.shots),
            "hits": str(self.stats.hits),
            "acc": f"{acc:.1f}%",
            "score": f"{self.stats.score:.0f}",
        }

        self._set_state("run_summary")

    def _apply_text_input(self):
        if not self.active_input_key:
            return

        key = self.active_input_key
        txt = self.input_buffer.strip()
        if txt == "":
            self.active_input_key = None
            self.input_buffer = ""
            return

        p = self._profile()
        aspect = self.width / self.height

        try:
            value = float(txt)
        except ValueError:
            self.active_input_key = None
            self.input_buffer = ""
            return

        if key in self.settings_numeric_keys:
            lo, hi = self.settings_numeric_keys[key]
            value = max(lo, min(hi, value))

        if key == "hipfire_sens":
            p["hipfire_sens"] = value
        elif key == "ads_sens":
            p["ads_sens"] = value
        elif key == "dpi":
            p["dpi"] = value
        elif key == "yaw":
            p["yaw"] = value
        elif key == "fov_h_deg":
            p["fov_h_deg"] = value
        elif key == "fov_v":
            p["fov_h_deg"] = self._fov_v_to_h(value, aspect)
        elif key == "crosshair_size":
            self.crosshair.size = int(round(value))
        elif key == "crosshair_thickness":
            self.crosshair.thickness = int(round(value))
        elif key == "crosshair_gap":
            self.crosshair.gap = int(round(value))
        elif key == "crosshair_red":
            _, g, b = self.crosshair.color
            self.crosshair.color = (int(round(value)), g, b)
        elif key == "crosshair_green":
            r, _, b = self.crosshair.color
            self.crosshair.color = (r, int(round(value)), b)
        elif key == "crosshair_blue":
            r, g, _ = self.crosshair.color
            self.crosshair.color = (r, g, int(round(value)))
        elif key == "master_volume":
            self.master_volume = value
            self._apply_sound_volumes()
        elif key == "gun_volume":
            self.gun_volume = value
            self._apply_sound_volumes()
        elif key == "hit_volume":
            self.hit_volume = value
            self._apply_sound_volumes()

        self.active_input_key = None
        self.input_buffer = ""

    def _handle_click_action(self, action: str, payload: str | None):
        if action == "main_play":
            self._start_run()
        elif action == "main_map":
            self._set_state("map_select")
        elif action == "main_settings":
            self._open_settings("main_menu")
        elif action == "main_scores":
            self._set_state("scores")
        elif action == "main_quit":
            self.running = False
        elif action == "map_pick" and payload:
            self.current_map = payload
            self.map_index = self.maps.index(payload)
            self._init_map()
        elif action == "duration_pick" and payload is not None:
            idx = int(payload)
            self.duration_index = max(0, min(len(self.durations) - 1, idx))
        elif action == "start_run":
            self._start_run()
        elif action == "back_main":
            self._set_state("main_menu")
        elif action == "scores_clear":
            self.score_history.clear()
            self.high_scores = self._default_high_scores()
            self._save_scores()
        elif action == "settings_edit" and payload:
            self.active_input_key = payload
            self.input_buffer = self._format_setting_value(payload)
        elif action == "game_cycle" and payload:
            self._switch_game(int(payload))
        elif action == "dot_toggle":
            self.crosshair.dot = not self.crosshair.dot
        elif action == "sound_toggle":
            self.sound_enabled = not self.sound_enabled
        elif action == "settings_save":
            self._save_profiles()
        elif action == "settings_back":
            if self.settings_origin == "playing":
                self._set_state("playing")
            else:
                self._set_state("main_menu")
        elif action == "summary_play_again":
            self._start_run()
        elif action == "summary_scores":
            self._set_state("scores")
        elif action == "summary_menu":
            self._set_state("main_menu")

    def _handle_mouse_click(self, pos):
        for rect, action, payload in reversed(self.click_regions):
            if rect.collidepoint(pos):
                self._handle_click_action(action, payload)
                return

        if self.screen_state == "settings":
            self.active_input_key = None
            self.input_buffer = ""

    def _handle_keydown(self, event):
        if event.key == pygame.K_F10:
            self.running = False
            return

        if self.screen_state == "playing":
            if event.key == pygame.K_ESCAPE:
                self._open_settings("playing")
            return

        if self.active_input_key:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._apply_text_input()
                return
            if event.key == pygame.K_BACKSPACE:
                self.input_buffer = self.input_buffer[:-1]
                return
            if event.key == pygame.K_ESCAPE:
                self.active_input_key = None
                self.input_buffer = ""
                return
            if event.unicode and event.unicode in "0123456789.-":
                self.input_buffer += event.unicode
            return

        if event.key == pygame.K_ESCAPE:
            if self.screen_state in ("settings", "map_select", "scores", "run_summary", "run_countdown"):
                if self.screen_state == "settings" and self.settings_origin == "playing":
                    self._set_state("playing")
                else:
                    self._set_state("main_menu")
            elif self.screen_state == "main_menu":
                self.running = False

    def run(self):
        while self.running:
            dt = self.clock.tick(240) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_keydown(event)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.screen_state == "playing":
                        if event.button == 1:
                            self._handle_training_click()
                        elif event.button == 3:
                            self.ads_held = True
                    else:
                        if event.button == 1:
                            self._handle_mouse_click(event.pos)
                elif event.type == pygame.MOUSEBUTTONUP:
                    if self.screen_state == "playing" and event.button == 3:
                        self.ads_held = False
                elif event.type == pygame.MOUSEWHEEL:
                    if self.screen_state == "settings":
                        self.settings_scroll = max(0.0, self.settings_scroll - (event.y * 24.0))

            if self.screen_state == "playing":
                self._update_mouse()
                self._update_weapon(dt)
                self.time_left = max(0.0, self.time_left - dt)

                if self.current_map == "reaction" and self.reaction_waiting:
                    now = pygame.time.get_ticks() / 1000.0
                    if now >= self.reaction_spawn_at:
                        self.targets = [self._spawn_target(26, cluster_scale=0.24)]
                        self.reaction_waiting = False
                        self.reaction_spawn_at = now

                if self.current_map == "tracking":
                    self._update_tracking(dt)

                if self.time_left <= 0.0:
                    self._finish_run()

            if self.screen_state == "run_countdown":
                self._update_mouse()
                self._update_weapon(dt)
                self.countdown_left = max(0.0, self.countdown_left - dt)
                if self.countdown_left <= 0.0:
                    self._set_state("playing")

            if self.screen_state == "main_menu":
                self._draw_main_menu()
            elif self.screen_state == "map_select":
                self._draw_map_select()
            elif self.screen_state == "settings":
                self._draw_settings()
            elif self.screen_state == "scores":
                self._draw_scores()
            elif self.screen_state == "run_summary":
                self._draw_run_summary()
            elif self.screen_state == "run_countdown":
                self._draw_countdown()
            elif self.screen_state == "playing":
                self._draw_training()

            pygame.display.flip()

        pygame.quit()


if __name__ == "__main__":
    AimLiteApp().run()
