# FIFA World Cup 2026 Fan Experience App — Implementation Plan

## Context

**Why:** Pivoting from a B2B venue intelligence simulator to a B2C fan engagement app for FIFA World Cup 2026. The existing project (`apps/web/` + `apps/api/`) remains untouched on `main`. All new development happens on branch `antoni/fan-app`. The new app lives in `apps/fan/` within the same monorepo.

**Git strategy:** Create branch `antoni/fan-app` from `main`. Build a new project structure on this branch. Reuse data from `main` (team traits, match schedule, city info) but build a new standalone app. The `main` branch stays clean.

**Owner scope:** Registration + Games module + Bracket module (other team members handle Monterrey check-in, live scores, event scraping).

**Outcome:** A mobile-first web app where fans register, play daily trivia, compete in bracket predictions with friends, and share results virally.

**Distribution:** Friends/personal use, not commercial.

---

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend/DB | **Supabase** | Auth, real-time, PostgreSQL, free tier. No custom backend needed for games/brackets |
| Navigation | **React Router v7** | Real URLs, shareable links, back button |
| State mgmt | **Zustand** | Lightweight, avoids prop drilling across routes |
| Games depth | **Mixed** | Quick trivia (5-10s) + one arcade hero game (Score the Goal) |
| Drag-and-drop | **@dnd-kit** | React 19 compatible, replaces unmaintained react-beautiful-dnd |
| Animations | **Framer Motion** | Gesture support for flick-to-shoot, page transitions |
| Styling | **Vanilla CSS + custom properties** | Consistent with existing repo pattern, no Tailwind |
| Bracket scoring | **Tiered** | Winner=5pts, exact score=15pts, group position=3pts, perfect group=20pts bonus |
| Hero feature | **Daily World Cup Challenge** | 5 daily questions, Wordle-style sharing, global+nation+friend leaderboards |
| Color palette | **FIFA tournament energy** | Electric Blue, Pitch Green, Gold, White backgrounds |

---

## File Structure

The new app lives in `apps/fan/` — completely separate from `apps/web/` and `apps/api/`. Shared data from `data/seed/` is imported at build time.

```
apps/fan/
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  public/
    manifest.json                     # PWA manifest
    icons/                            # App icons 192/512
    flags/                            # 48x48 SVG flag images for 28+ teams
    city-photos/                      # Host city photos for Guess the City
    player-silhouettes/               # Player silhouettes for Guess the Player
  src/
    main.tsx                          # Entry: RouterProvider + SupabaseProvider
    router.tsx                        # React Router route definitions
    App.tsx                           # Layout shell: TopBar + <Outlet /> + BottomNav

    lib/
      supabase.ts                     # Supabase client (typed)
      auth.ts                         # signUp, signIn, signOut, onAuthChange
      constants.ts                    # TEAMS[], MATCHES[], GROUPS[] (from data/seed/)
      bracket-engine.ts               # FIFA tiebreaker calc, scoring, group standings
      daily-challenge.ts              # Deterministic question selection, share text gen
      game-physics.ts                 # Score the Goal: trajectory, collision, keeper AI
      format.ts                       # Number/date formatters

    hooks/
      useAuth.ts                      # Auth state, wraps supabase.auth
      useProfile.ts                   # Fetch/update profile
      useBracket.ts                   # Bracket CRUD + realtime
      useLeaderboard.ts               # Leaderboard queries with pagination
      useDailyChallenge.ts            # Today's challenge, submission, results
      useGameScores.ts                # Submit/fetch mini-game scores

    stores/
      auth-store.ts                   # Zustand: auth state + profile
      bracket-store.ts                # Zustand: bracket editing state
      game-store.ts                   # Zustand: active game session

    components/
      ui/                             # Design system primitives
        Button.tsx
        Card.tsx
        Badge.tsx
        Input.tsx
        Avatar.tsx
        BottomNav.tsx
        TopBar.tsx
        Modal.tsx
        TeamBadge.tsx                 # Flag + name + color stripe
        ProgressRing.tsx              # Circular countdown timer
        ShareCard.tsx                 # Wordle-style shareable result
        DragList.tsx                  # Reorderable list for group predictions

      registration/
        RegistrationScreen.tsx
        TeamPicker.tsx
        NicknameInput.tsx

      home/
        HomeScreen.tsx                # Daily challenge prompt + next match + quick links
        MatchCountdown.tsx
        QuickLinks.tsx

      games/
        GamesHub.tsx                  # Game selection grid
        ScoreTheGoal.tsx              # Canvas penalty shootout
        GoalCanvas.tsx                # HTML5 Canvas rendering layer
        GuessThePlayer.tsx
        GuessTheFlag.tsx
        GuessTheCity.tsx
        DailyChallenge.tsx            # Hero feature: 5-question flow
        DailyChallengeResult.tsx      # Wordle-style result + share
        QuestionCard.tsx              # Reusable question layout
        AnswerButton.tsx              # Animated correct/wrong state
        CountdownTimer.tsx
        GameOverCard.tsx
        MiniLeaderboard.tsx

      bracket/
        BracketHub.tsx                # Mode selector + league links
        GroupStageEditor.tsx          # 12 groups, drag or input scores
        GroupCard.tsx                  # Single group with 4 teams
        KnockoutBracket.tsx           # R32 → Final visual tree (horiz scroll)
        KnockoutMatchCard.tsx         # Tap to advance winner
        ScoreInput.tsx                # Advanced mode: home/away score inputs
        BracketLeaderboard.tsx
        BracketComparison.tsx         # Side-by-side vs friend
        PrivateLeagueCreate.tsx
        PrivateLeagueJoin.tsx
        LeagueList.tsx

      leaderboard/
        GlobalLeaderboard.tsx
        NationLeaderboard.tsx
        FriendsLeaderboard.tsx
        LeaderboardRow.tsx

      shared/
        ProtectedRoute.tsx            # Redirect to /register if not authenticated
        ErrorBoundary.tsx
        LoadingSpinner.tsx

    styles/
      tokens.css                      # CSS custom properties (colors, spacing, type)
      global.css                      # Reset + base styles + mobile-first layout
      components.css                  # UI primitive styles
      games.css                       # Game-specific styles
      bracket.css                     # Bracket-specific styles

    assets/
      questions/
        players.json                  # 200+ player questions
        flags.json                    # 28 team flag questions
        cities.json                   # 6 city photo questions
        mixed.json                    # Daily challenge pool (500+ questions)

    test/
      setup.ts
      fixtures/
        teams.ts
        brackets.ts
        daily-challenge.ts
```

Root `package.json` updated to add `apps/fan` to workspaces:
```json
"workspaces": ["apps/web", "apps/fan"]
```

---

## Design System

### Color Palette (tokens.css)

```css
:root {
  /* Primary palette */
  --color-electric-blue: #1A56DB;
  --color-pitch-green: #22C55E;
  --color-gold: #F59E0B;
  --color-white: #FFFFFF;
  --color-near-black: #0F172A;

  /* Semantic */
  --color-bg: #FFFFFF;
  --color-bg-secondary: #F8FAFC;
  --color-bg-tertiary: #F1F5F9;
  --color-text-primary: #0F172A;
  --color-text-secondary: #475569;
  --color-text-muted: #94A3B8;
  --color-border: #E2E8F0;

  /* Interactive */
  --color-primary: #1A56DB;
  --color-primary-hover: #1E40AF;
  --color-success: #22C55E;
  --color-success-light: #DCFCE7;
  --color-danger: #EF4444;
  --color-danger-light: #FEE2E2;
  --color-warning: #F59E0B;
  --color-warning-light: #FEF3C7;

  /* Typography */
  --font-sans: "Space Grotesk", "Segoe UI", system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", monospace;
  --text-xs: 0.75rem;   --text-sm: 0.875rem;  --text-base: 1rem;
  --text-lg: 1.125rem;  --text-xl: 1.25rem;   --text-2xl: 1.5rem;
  --text-3xl: 1.875rem; --text-4xl: 2.25rem;

  /* Spacing */
  --space-1: 0.25rem; --space-2: 0.5rem;  --space-3: 0.75rem;
  --space-4: 1rem;    --space-6: 1.5rem;  --space-8: 2rem;
  --space-10: 2.5rem; --space-12: 3rem;

  /* Radius */
  --radius-sm: 8px;  --radius-md: 12px;  --radius-lg: 16px;
  --radius-xl: 20px; --radius-full: 999px;

  /* Shadows (light theme) */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
  --shadow-lg: 0 12px 32px rgba(0,0,0,0.12);
  --shadow-card: 0 2px 8px rgba(0,0,0,0.06);

  /* Layout */
  --nav-height: 64px;
  --safe-bottom: env(safe-area-inset-bottom, 0px);
}
```

### Component Patterns

- **Buttons**: 48px min touch target, `border-radius: var(--radius-full)`, full-width on mobile
  - `btn-primary`: Electric Blue bg, white text
  - `btn-secondary`: White bg, Electric Blue border
  - `btn-team`: Dynamic team color bg, white text
- **Cards**: White bg, `var(--shadow-card)`, `var(--radius-lg)` corners
  - `card-highlight`: Electric Blue left border (for Daily Challenge)
  - `card-team`: Team color gradient top border
- **Team Badge**: 24x24 flag + team name + thin color bar
- **Inputs**: 48px height, `var(--radius-md)`, focus = blue border
- **Bottom Nav**: Fixed, 4 items (Home/Games/Bracket/Leaders), white bg, top border

---

## Supabase Schema (SQL)

```sql
-- PROFILES
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  nickname TEXT NOT NULL UNIQUE,
  email TEXT,
  phone TEXT,
  team_id TEXT NOT NULL,
  team_name TEXT NOT NULL,
  team_color TEXT NOT NULL,
  avatar_url TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- BRACKETS
CREATE TYPE bracket_mode AS ENUM ('simple', 'advanced');

CREATE TABLE brackets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  mode bracket_mode NOT NULL DEFAULT 'simple',
  total_points INTEGER NOT NULL DEFAULT 0,
  is_locked BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (user_id, mode)
);

-- GROUP PREDICTIONS (drag order)
CREATE TABLE bracket_groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  bracket_id UUID NOT NULL REFERENCES brackets(id) ON DELETE CASCADE,
  group_letter CHAR(1) NOT NULL,
  predicted_order TEXT[] NOT NULL,  -- ["argentina","austria","jordan","playoff_a"]
  UNIQUE (bracket_id, group_letter)
);

-- MATCH PREDICTIONS (knockout + advanced scores)
CREATE TABLE bracket_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  bracket_id UUID NOT NULL REFERENCES brackets(id) ON DELETE CASCADE,
  match_id TEXT NOT NULL,
  stage TEXT NOT NULL,              -- "group","r32","r16","qf","sf","final"
  predicted_home_score INTEGER,     -- NULL in simple mode for group stage
  predicted_away_score INTEGER,
  predicted_winner TEXT,
  points_awarded INTEGER DEFAULT 0,
  UNIQUE (bracket_id, match_id)
);

-- GAME SCORES
CREATE TYPE game_type AS ENUM ('score_the_goal','guess_the_player','guess_the_flag','guess_the_city');

CREATE TABLE game_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  game game_type NOT NULL,
  score INTEGER NOT NULL,
  metadata JSONB DEFAULT '{}',     -- { streak: 5, time_ms: 4200 }
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_game_leaderboard ON game_scores(game, score DESC);

-- DAILY CHALLENGES
CREATE TABLE daily_challenges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  challenge_date DATE NOT NULL UNIQUE,
  questions JSONB NOT NULL          -- array of 5 question objects
);

CREATE TABLE daily_challenge_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  challenge_date DATE NOT NULL,
  answers JSONB NOT NULL,           -- [{question_idx, chosen, correct, time_ms}]
  score INTEGER NOT NULL,           -- 0-5
  total_time_ms INTEGER NOT NULL,
  UNIQUE (user_id, challenge_date)
);
CREATE INDEX idx_dcr_leaderboard ON daily_challenge_results(challenge_date, score DESC, total_time_ms ASC);

-- PRIVATE LEAGUES
CREATE TABLE private_leagues (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  invite_code TEXT NOT NULL UNIQUE DEFAULT substr(md5(random()::text), 1, 8),
  created_by UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE league_members (
  league_id UUID REFERENCES private_leagues(id) ON DELETE CASCADE,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  joined_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (league_id, user_id)
);

-- LEADERBOARD VIEWS
CREATE VIEW bracket_leaderboard AS
  SELECT b.user_id, p.nickname, p.team_id, p.team_color, b.mode, b.total_points
  FROM brackets b JOIN profiles p ON p.id = b.user_id
  ORDER BY b.total_points DESC;

CREATE VIEW daily_challenge_leaderboard AS
  SELECT dcr.user_id, p.nickname, p.team_id, p.team_color,
         dcr.challenge_date, dcr.score, dcr.total_time_ms
  FROM daily_challenge_results dcr JOIN profiles p ON p.id = dcr.user_id
  ORDER BY dcr.score DESC, dcr.total_time_ms ASC;

-- RLS policies (enable on all tables)
-- profiles: read all, update/insert own
-- brackets/groups/entries: read all, manage own
-- game_scores: read all, insert own
-- daily_challenge_results: read all, insert own
-- private_leagues: read all, create own
-- league_members: read all, join/leave own
```

### Bracket Scoring Functions (Supabase Edge Functions)

```sql
-- Called when real match results come in
-- Correct winner = 5pts, exact score = 15pts
-- Correct group position = 3pts, perfect group = 20pts bonus
CREATE OR REPLACE FUNCTION calculate_bracket_points(
  p_match_id TEXT, p_actual_winner TEXT,
  p_actual_home_score INT, p_actual_away_score INT
) RETURNS void AS $$
BEGIN
  UPDATE bracket_entries SET points_awarded = CASE
    WHEN predicted_winner = p_actual_winner
     AND predicted_home_score = p_actual_home_score
     AND predicted_away_score = p_actual_away_score THEN 15
    WHEN predicted_winner = p_actual_winner THEN 5
    ELSE 0 END
  WHERE match_id = p_match_id;
  -- Recalculate bracket totals
  UPDATE brackets SET total_points = (
    SELECT COALESCE(SUM(points_awarded), 0)
    FROM bracket_entries WHERE bracket_entries.bracket_id = brackets.id
  ), updated_at = now();
END; $$ LANGUAGE plpgsql SECURITY DEFINER;
```

---

## ASCII Wireframes (375px Mobile — for Figma AI prompts)

### Registration Screen
```
+---------------------------------------+
|           [FIFA WC 2026 logo]         |
|                                       |
|         Pick Your Experience          |
|                                       |
|  +----------------------------------+ |
|  | Nickname                         | |
|  | [_____________________________]  | |
|  +----------------------------------+ |
|                                       |
|  +----------------------------------+ |
|  | Email or Phone                   | |
|  | [_____________________________]  | |
|  +----------------------------------+ |
|                                       |
|  Your Team                            |
|  +--------+ +--------+ +--------+    |
|  |[flag]  | |[flag]  | |[flag]  |    |
|  |  ARG   | |  BRA   | |  ENG   |    |
|  +--------+ +--------+ +--------+    |
|  +--------+ +--------+ +--------+    |
|  |  GER   | |  JPN   | |  MEX   |    |
|  +--------+ +--------+ +--------+    |
|  ... (scrollable 4-col grid, 28+) .. |
|                                       |
|  [========= LET'S GO ============]   |
|  (primary btn, team color bg)         |
+---------------------------------------+
```

### Home Screen
```
+---------------------------------------+
|  Hi, Antoni!            [ARG flag]    |
|  World Cup starts in 82 days          |
+---------------------------------------+
|                                       |
|  +----------------------------------+ |
|  | DAILY CHALLENGE            NEW   | |
|  | 5 questions - Same for everyone  | |
|  | [========= PLAY NOW =========]   | |
|  +----------------------------------+ |
|                                       |
|  +----------------------------------+ |
|  | NEXT MATCH                       | |
|  | [NED] Netherlands vs Japan [JPN] | |
|  | Jun 14 - 6:00 PM - AT&T Stadium | |
|  +----------------------------------+ |
|                                       |
|  +--------+ +--------+               |
|  | Games  | |Bracket |               |
|  +--------+ +--------+               |
|  +--------+ +--------+               |
|  |Leaders | |Profile |               |
|  +--------+ +--------+               |
|                                       |
+---------------------------------------+
| [Home] [Games] [Bracket] [Leaders]    |
+---------------------------------------+
```

### Games Hub
```
+---------------------------------------+
|  <- Games                             |
+---------------------------------------+
|                                       |
|  +----------------------------------+ |
|  | [goal icon]  Score the Goal      | |
|  | Flick-to-shoot penalty kicks     | |
|  | Best: 1,250 pts                  | |
|  +----------------------------------+ |
|                                       |
|  +-----------+ +-----------+          |
|  |[silhouet] | |[flag img] |          |
|  | Guess the | | Guess the |          |
|  | Player    | | Flag      |          |
|  | Best: 8/10| | Best: 10  |          |
|  +-----------+ +-----------+          |
|                                       |
|  +-----------+ +-----------+          |
|  |[city img] | |[star]     |          |
|  | Guess the | | Daily     |          |
|  | City      | | Challenge |          |
|  | Best: 6/6 | | Streak: 5 |          |
|  +-----------+ +-----------+          |
|                                       |
+---------------------------------------+
| [Home] [Games] [Bracket] [Leaders]    |
+---------------------------------------+
```

### Score the Goal (Gameplay — Full Physics)

**Shot mechanics (3 inputs from a single gesture):**
1. **Direction** — where you flick toward (aim at goal corners)
2. **Power** — flick speed/distance (slow = weak lob, fast = rocket)
3. **Spin (podkręcenie)** — curve of the flick gesture (straight line = no spin, curved swipe = ball curves in flight)
4. **Contact point** — where on the ball you start the swipe (top = dipping shot, bottom = lofted chip, left/right edge = side spin)

**Physics model (`game-physics.ts`):**
- Ball trajectory: 2D projectile with drag + Magnus effect (spin → lateral force)
- Contact point → launch angle + spin axis
- Power → initial velocity (capped)
- Spin → curvature over time (visible arc on canvas)
- Goalkeeper AI: reads power + direction, dives with reaction delay
- Post/crossbar collisions: ball bounces realistically
- Net animation on goal

**Visual feedback during shot:**
- Aiming reticle appears on touch-down (shows where ball will go)
- Power meter fills based on swipe speed
- Spin indicator: curved arrow shows predicted curve
- Slow-motion replay on goal (0.3s)

```
+---------------------------------------+
|  Score: 350    Lives: OOO   x3 combo  |
+---------------------------------------+
|                                       |
|  +----------------------------------+ |
|  |    +---------------------------+  | |
|  |    |  TOP-L  |  TOP-MID | TOP-R | | |
|  |    |---------|----------|-------| | |
|  |    |  BOT-L  |  BOT-MID | BOT-R | | |
|  |    +---------|----------|-------+ | |
|  |         [GOALKEEPER]              | |
|  |    +---------------------------+  | |
|  |                                   | |
|  |         ~ ball trajectory ~       | |
|  |        (curved if spin applied)   | |
|  |                                   | |
|  |    [PWR =========>]  [SPIN: ~)]   | |
|  |                                   | |
|  |            ( O )                  | |
|  |     [touch here, swipe to shoot]  | |
|  |     [contact point = where you    | |
|  |      touch on the ball]           | |
|  +----------------------------------+ |
|  (HTML5 Canvas - touch gesture area)  |
+---------------------------------------+
```

**Difficulty progression:**
- Level 1-3: Keeper slow, big goal zones, power/spin less critical
- Level 4-7: Keeper reads direction faster, must use spin to beat
- Level 8+: Keeper anticipates, wind factor, must combine spin + power + placement
- Boss rounds (every 5): Famous keeper (Neuer, Courtois) with unique dive patterns

### Guess the Player
```
+---------------------------------------+
|  <- Guess the Player     7/10         |
+---------------------------------------+
|  [====================] (10s timer)   |
|                                       |
|  +----------------------------------+ |
|  |    +------------------------+    | |
|  |    |   [SILHOUETTE or       |    | |
|  |    |    PARTIAL PHOTO]      |    | |
|  |    +------------------------+    | |
|  |                                  | |
|  |  Who is this player?             | |
|  |                                  | |
|  |  +------------------------------+| |
|  |  | A. Lionel Messi              || |
|  |  +------------------------------+| |
|  |  +------------------------------+| |
|  |  | B. Cristiano Ronaldo         || |
|  |  +------------------------------+| |
|  |  +------------------------------+| |
|  |  | C. Kylian Mbappe             || |
|  |  +------------------------------+| |
|  |  +------------------------------+| |
|  |  | D. Neymar Jr                 || |
|  |  +------------------------------+| |
|  +----------------------------------+ |
+---------------------------------------+
```

### Daily Challenge Result (Wordle-style)
```
+---------------------------------------+
|  DAILY WORLD CUP CHALLENGE            |
|  March 24, 2026                       |
+---------------------------------------+
|                                       |
|           4 / 5                       |
|                                       |
|    [G] [G] [R] [G] [G]               |
|    green=correct  red=wrong           |
|                                       |
|    Total time: 28.4s                  |
|                                       |
|  +----------------------------------+ |
|  | WC Daily #42 - Mar 24            | |
|  | [G][G][R][G][G] 4/5 28.4s       | |
|  | [======= SHARE RESULT ========] | |
|  +----------------------------------+ |
|                                       |
|  Today's Leaderboard                  |
|  +----------------------------------+ |
|  | 1. @carlos    5/5  12.1s  [ARG] | |
|  | 2. @maria     5/5  18.3s  [BRA] | |
|  | 3. @antoni    4/5  28.4s  [ARG] | |
|  +----------------------------------+ |
|  [See Full Leaderboard ->]            |
|                                       |
+---------------------------------------+
| [Home] [Games] [Bracket] [Leaders]    |
+---------------------------------------+
```

### Bracket Hub
```
+---------------------------------------+
|  <- My Bracket                        |
+---------------------------------------+
|  +----------------------------------+ |
|  | Your Points: 47    Rank: #128    | |
|  | [ARG] Argentina Fans: #12        | |
|  +----------------------------------+ |
|                                       |
|  Mode                                 |
|  +---------------+ +---------------+  |
|  |   SIMPLE      | |   ADVANCED    |  |
|  |  Drag & pick  | | Input scores  |  |
|  +---------------+ +---------------+  |
|                                       |
|  [======= EDIT GROUPS =========]      |
|  [======= EDIT KNOCKOUT =======]      |
|                                       |
|  Your Leagues                         |
|  +----------------------------------+ |
|  | CU Boulder Squad       #3 of 8  | |
|  | Family League           #1 of 5  | |
|  +----------------------------------+ |
|  [+ Create League]  [Join League]     |
|                                       |
+---------------------------------------+
| [Home] [Games] [Bracket] [Leaders]    |
+---------------------------------------+
```

### Group Stage Editor (Simple — Drag)
```
+---------------------------------------+
|  <- Group Stage       Lock: [toggle]  |
+---------------------------------------+
|  Drag teams to predict final order    |
|                                       |
|  Group A                              |
|  +----------------------------------+ |
|  | 1. [flag] Argentina     [=drag]  | |
|  | 2. [flag] Austria       [=drag]  | |
|  | 3. [flag] Jordan        [=drag]  | |
|  | 4. [flag] Playoff A     [=drag]  | |
|  +----------------------------------+ |
|                                       |
|  Group B                              |
|  +----------------------------------+ |
|  | 1. [flag] Brazil        [=drag]  | |
|  | 2. [flag] Scotland      [=drag]  | |
|  | 3. [flag] Colombia      [=drag]  | |
|  | 4. [flag] Playoff D     [=drag]  | |
|  +----------------------------------+ |
|  ... (12 groups, scrollable) ...      |
|                                       |
|  [========= SAVE & CONTINUE ======]  |
+---------------------------------------+
| [Home] [Games] [Bracket] [Leaders]    |
+---------------------------------------+
```

### Group Stage Editor (Advanced — Scores)
```
+---------------------------------------+
|  <- Group A Scores    Auto-calc: ON   |
+---------------------------------------+
|  Matchday 1                           |
|  +----------------------------------+ |
|  | [ARG] Argentina  [2]-[0] Austria | |
|  | [JOR] Jordan     [1]-[1] Plf. A | |
|  +----------------------------------+ |
|  Matchday 2                           |
|  +----------------------------------+ |
|  | [ARG] Argentina  [3]-[1] Jordan  | |
|  | [AUT] Austria    [2]-[0] Plf. A | |
|  +----------------------------------+ |
|  Matchday 3                           |
|  +----------------------------------+ |
|  | [ARG] Argentina  [1]-[0] Plf. A | |
|  | [AUT] Austria    [0]-[2] Jordan  | |
|  +----------------------------------+ |
|                                       |
|  Calculated Standings                 |
|  +----------------------------------+ |
|  | # Team       Pts  GD  GF        | |
|  | 1 Argentina   9   +5   6        | |
|  | 2 Jordan      4   +1   4        | |
|  | 3 Austria     3   +0   2        | |
|  | 4 Playoff A   0   -6   1        | |
|  +----------------------------------+ |
+---------------------------------------+
| [Home] [Games] [Bracket] [Leaders]    |
+---------------------------------------+
```

### Knockout Bracket (Horizontal Scroll)
```
+---------------------------------------+
|  <- Knockout Bracket                  |
+---------------------------------------+
|  R32    R16    QF    SF    F          |
|  <---- horizontally scrollable ---->  |
|                                       |
|  +------+                             |
|  |ARG  3| \                           |
|  +------+  +------+                   |
|  |AUS  1| /|ARG   | \                 |
|  +------+  +------+  +------+        |
|             |ENG   | /|ARG   |        |
|  +------+  +------+  +------+        |
|  |ENG  2| /                    \      |
|  +------+                       +---+ |
|  |JPN  0| \                     |ARG| |
|  +------+  ...                  +---+ |
|                                       |
|  Tap a match to pick the winner       |
+---------------------------------------+
| [Home] [Games] [Bracket] [Leaders]    |
+---------------------------------------+
```

### Leaderboard
```
+---------------------------------------+
|  Leaderboards                         |
+---------------------------------------+
|  [Global] [My Nation] [Friends]       |
+---------------------------------------+
|  Bracket Rankings                     |
|  +----------------------------------+ |
|  | # | Player   | Team | Points    | |
|  | 1 | @carlos  | ARG  | 127       | |
|  | 2 | @maria   | BRA  | 119       | |
|  | 3 | @james   | ENG  | 115       | |
|  | ...                               | |
|  | 128| @antoni  | ARG  |  47       | |
|  +----------------------------------+ |
|                                       |
|  Daily Challenge Streaks              |
|  +----------------------------------+ |
|  | 1 | @carlos  | ARG  | 14 days   | |
|  | 2 | @antoni  | ARG  | 5 days    | |
|  +----------------------------------+ |
|                                       |
|  Score the Goal High Scores           |
|  +----------------------------------+ |
|  | 1 | @james   | ENG  | 2,450     | |
|  | 2 | @maria   | BRA  | 1,890     | |
|  +----------------------------------+ |
+---------------------------------------+
| [Home] [Games] [Bracket] [Leaders]    |
+---------------------------------------+
```

---

## Dependencies (apps/fan/package.json)

```json
{
  "dependencies": {
    "react": "^19.2.4",
    "react-dom": "^19.2.4",
    "react-router-dom": "^7.0.0",
    "@supabase/supabase-js": "^2.45.0",
    "zustand": "^5.0.0",
    "framer-motion": "^11.5.0"
  },
  "devDependencies": {
    "@dnd-kit/core": "^6.3.0",
    "@dnd-kit/sortable": "^10.0.0",
    "@dnd-kit/utilities": "^4.0.0",
    "@vitejs/plugin-react": "^4.5.4",
    "@types/react": "^19.2.4",
    "@types/react-dom": "^19.2.4",
    "typescript": "^5.9.3",
    "vite": "^7.3.1",
    "vitest": "^4.0.18",
    "@testing-library/react": "^16.3.2",
    "@testing-library/jest-dom": "^6.9.1",
    "jsdom": "^28.1.0"
  }
}
```

**Not needed** (dropped from old app): deck.gl, Google Maps loader, maplibre-gl, recharts, react-map-gl

---

## Reusing Existing Data

| Source | What | How |
|--------|------|-----|
| `apps/api/app/data_loader.py` TEAM_TRAITS (L41-72) | 28 team colors, fan_strength, spend | Extract into `src/lib/constants.ts` as TEAMS[] |
| `data/seed/world_cup_schedule.csv` | 27 matches across 6 cities | Parse into MATCHES[] constant with groups inferred |
| `data/seed/matches.json` | Match metadata, venue capacities | Merge into MATCHES[] |
| `data/cities/*/base.json` | City names, venues, coordinates | Use for Guess the City game + match display |

The 2026 WC has 48 teams in 12 groups. The existing data covers 6 host cities and 27 matches. For the complete app we need:
- **48 teams** (42 qualified + 6 playoff slots) with flags, colors, group assignments
- **All 16 host cities** (11 USA + 3 Mexico + 2 Canada)
- **Full group stage schedule** (72 matches) + knockout structure (32 matches)
- **240 players** (48 teams × 5 top players each)

---

## Asset Collection Strategy

### Flags (48 nations)
- **Method:** Install `flag-icons` npm package (open-source SVGs for all countries)
- **Effort:** Zero manual work — just `npm install flag-icons` and reference by country code
- **Fallback for playoff slots:** Generic "TBD" placeholder flag

### Player Images (240 players)
- **Primary API:** TheSportsDB (thesportsdb.com) — completely free, no request cap, no signup needed
  - Endpoint: `https://www.thesportsdb.com/api/v1/json/3/searchplayers.php?t={team_name}`
  - Returns player objects with `strCutout` (transparent PNG) and `strThumb` (headshot)
  - Transparent cutouts are ideal for the silhouette game mechanic
- **Script:** `scripts/fetch-players.py` that:
  1. Queries 48 national teams from TheSportsDB
  2. Picks top 5 players per team
  3. Downloads cutout PNGs to `public/players/{team_id}/{player_name}.png`
  4. Generates `src/assets/questions/players.json` with full metadata
  5. Skips players without cutout images (some small nations may have 3-4 players instead of 5)
- **Silhouette in-game:** CSS `filter: brightness(0)` on the transparent cutout → removed on correct answer
- **Data file:** `src/assets/questions/players.json` with 240 entries:
  ```json
  { "id": "messi", "name": "Lionel Messi", "team": "argentina", "position": "Forward",
    "jersey": 10, "club": "Inter Miami", "hint": "8 Ballon d'Or winner", "image": "/players/argentina/messi.png" }
  ```
- **No API key needed** — TheSportsDB basic access is free
- **I will write the full 240-player dataset** with names, teams, positions, jersey numbers, clubs, and hints

### City Photos (16 host cities)
- **Method:** Download 3-5 recognizable photos per city from the web (stadiums, landmarks, skylines)
- **16 cities:**
  - USA (11): New York/NJ, Los Angeles, Dallas, Houston, Atlanta, Philadelphia, Miami, Seattle, San Francisco, Kansas City, Boston
  - Mexico (3): Mexico City, Monterrey, Guadalajara
  - Canada (2): Toronto, Vancouver
- **Storage:** `public/city-photos/{city_id}/1.jpg`, `2.jpg`, `3.jpg`
- **I will download these** using web search during Phase 2 implementation
- **Data file:** `src/assets/questions/cities.json` with city descriptions and photo refs

### Trivia Questions (200+)
- **Method:** I will write 200 interesting World Cup trivia questions covering:
  - All-time records and stats
  - Famous moments (Maradona's Hand of God, Zidane headbutt, etc.)
  - 2026 format changes (48 teams, 12 groups)
  - Host city facts
  - Player milestones
  - Rules and regulations
  - Cultural moments (chants, mascots, songs)
- **Format:** JSON with question, 4 options, correct answer index, explanation
- **Source:** Compiled from publicly available World Cup knowledge

---

## Daily Challenge Content Strategy

**Question bank:** 200+ hand-written questions stored as static JSON in `src/assets/questions/mixed.json`

**Categories (target counts):**
- World Cup History & Famous Moments: 50 questions
- Player Knowledge: 40 questions
- Team & Nation Trivia: 30 questions
- Geography/Venues/Host Cities: 30 questions
- Rules, Formats & 2026 Changes: 25 questions
- Cultural/Fun (chants, mascots, songs): 25 questions

**Daily selection algorithm** (deterministic, no server needed):
```typescript
function getDailyQuestions(date: Date): Question[] {
  const seed = hashString(date.toISOString().slice(0, 10)); // "2026-03-24"
  const rng = seededRandom(seed);  // mulberry32
  // Pick 5: 1 history + 1 player + 1 geography + 2 random
  // No repeats within 14-day window
  return selectDiverseQuestions(allQuestions, rng, 5);
}
```

Same date = same 5 questions for every user worldwide. No server required.

**Content generation plan:**
- Phase 1 (launch): 200 questions written by me (40 days of unique dailies)
- Phase 2: Use existing Gemini API key to batch-generate more if needed
- Phase 3: Community submissions (post-launch, if app grows)

---

## Implementation Phases

### Phase 0: Foundation (Days 1-2)
- Create and switch to branch `antoni/fan-app` from `main`
- Create `apps/fan/` with Vite + React + TypeScript scaffold
- Add to root workspace
- Set up Supabase project + run schema SQL
- Create `tokens.css` design system + `global.css` reset
- Create `router.tsx` with React Router
- Create `main.tsx` with providers
- Create `App.tsx` layout shell (TopBar + BottomNav + Outlet)
- Build all UI primitives (`components/ui/`)

### Phase 1: Registration (Days 3-4)
- `lib/supabase.ts` + `lib/auth.ts`
- `hooks/useAuth.ts` + `stores/auth-store.ts`
- `RegistrationScreen`, `NicknameInput`, `TeamPicker`
- `ProtectedRoute` wrapper
- `HomeScreen` with countdown and quick links
- Team constants from TEAM_TRAITS data
- Tests for registration flow

### Phase 2: Trivia Games (Days 5-7)
- Create question JSON banks (flags, players, cities)
- Build shared: `QuestionCard`, `AnswerButton`, `CountdownTimer`
- Build `GuessTheFlag` (simplest, proves pattern)
- Build `GuessTheCity` (reuses city data)
- Build `GuessThePlayer`
- Build `GamesHub` grid
- Build `GameOverCard` + `MiniLeaderboard`
- Wire scores to Supabase `game_scores`
- Tests

### Phase 3: Score the Goal Arcade (Days 8-10)
- `lib/game-physics.ts` (trajectory, keeper AI, collision)
- `GoalCanvas` (HTML5 Canvas rendering)
- `ScoreTheGoal` (touch flick detection via framer-motion)
- Difficulty progression (keeper gets smarter)
- Scoring: combo multiplier, distance bonus
- Wire to Supabase
- Tests

### Phase 4: Daily Challenge (Days 11-13)
- `lib/daily-challenge.ts` (seeded selection, share text)
- `DailyChallenge` 5-question flow
- `DailyChallengeResult` Wordle-style grid + share
- Copy-to-clipboard with formatted text
- Daily leaderboard view (global + nation + friends)
- Tests

### Phase 5: Bracket Simple Mode (Days 14-17)
- `lib/bracket-engine.ts` (48-team 12-group structure)
- `stores/bracket-store.ts`
- `GroupStageEditor` with @dnd-kit drag-to-reorder
- `GroupCard`
- `KnockoutBracket` horizontal scroll
- `KnockoutMatchCard` tap-to-advance
- Wire to Supabase brackets/groups/entries
- `BracketHub`
- Tests

### Phase 6: Bracket Advanced Mode (Days 18-20)
- `ScoreInput` component
- Extend GroupStageEditor for score input
- FIFA tiebreaker algorithm:
  - Points (W=3, D=1, L=0)
  - Goal difference
  - Goals scored
  - Head-to-head points → H2H GD
  - Fair play (random tiebreak fallback)
- Auto-calculate standings from scores
- Feed into knockout bracket
- Extensive tiebreaker tests (15+ cases)

### Phase 7: Social Features (Days 21-23)
- `PrivateLeagueCreate` + `PrivateLeagueJoin`
- `LeagueList`
- `BracketLeaderboard` (Global / Nation / League tabs)
- `BracketComparison` side-by-side view
- Supabase realtime subscriptions for live updates
- Tests

### Phase 8: Polish (Days 24-26)
- Responsive breakpoints (375 → 428 → 768 → 1024)
- Framer-motion animations (page transitions, score reveals)
- PWA manifest + offline trivia
- Performance: lazy-load canvas, code-split routes
- Accessibility: focus management, ARIA, contrast

---

## Mobile Development Workflow

- **Chrome DevTools**: Toggle Device Toolbar (Cmd+Shift+M), test at iPhone SE (375), iPhone 14 (390), iPhone 14 Pro Max (428)
- **VS Code Extension**: "Mobile Viewer" or "Responsive Viewer" for side-by-side preview
- **Vite**: Already serves on `127.0.0.1` — access from phone on same WiFi via `--host 0.0.0.0`
- **CSS strategy**: Mobile-first (`min-width` media queries only), `375px` base viewport

---

## Testing Strategy

| Layer | Tool | Focus |
|-------|------|-------|
| Unit | Vitest | bracket-engine.ts (15+ tiebreaker cases), daily-challenge.ts (determinism), game-physics.ts (trajectory) |
| Component | Vitest + RTL | Registration flow, QuestionCard interactions, GroupStageEditor drag, KnockoutMatchCard tap |
| Integration | Vitest + RTL | Full Daily Challenge flow (5 questions → result → share), Bracket create → edit → save |
| Mock strategy | Mock `lib/supabase` module | Return controlled data, same pattern as existing `App.test.tsx` mocking `lib/api` |

---

## Verification Checklist

After each phase, verify:
1. `npm run dev` from `apps/fan/` serves at `http://127.0.0.1:5174`
2. `npm run test` passes all new tests
3. Mobile viewport (375px) in Chrome DevTools looks correct
4. Supabase Dashboard shows data being written correctly
5. Existing `apps/web/` still runs independently on port 5173 (no regressions)

---

## Figma Workflow

Use the ASCII wireframes above as prompts for Figma AI generation:
1. Copy each wireframe into Figma AI (or a tool like Galileo AI / Uizard)
2. Apply the color palette: Electric Blue #1A56DB, Pitch Green #22C55E, Gold #F59E0B, White #FFFFFF
3. Use Space Grotesk font
4. Export as design tokens or screenshots
5. Share with Claude for pixel-perfect implementation

---

## Key Files to Create First

1. `apps/fan/package.json` — dependencies and scripts
2. `apps/fan/vite.config.ts` — dev server on port 5174, env from root
3. `apps/fan/src/lib/constants.ts` — TEAMS[] and MATCHES[] from existing data
4. `apps/fan/src/lib/supabase.ts` — Supabase client
5. `apps/fan/src/styles/tokens.css` — design system
6. `apps/fan/src/router.tsx` — all routes
7. `apps/fan/src/components/ui/` — primitive components
