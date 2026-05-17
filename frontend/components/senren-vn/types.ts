export type SenrenMode = "monitor" | "story" | "local" | "";

export type ApiErrorPayload = {
  detail?: string;
};

export interface RecentChoice {
  context?: string;
  option_text?: string;
  location?: string;
  characters?: string[];
}

export interface LiveState {
  session_id: string;
  mode: string;
  question_count: number;
  current_route: string | null;
  core_mu: Record<string, number>;
  top_dimensions: { key: string; label: string; score: number }[];
  character_affinity: Record<string, number>;
  recent_choices: RecentChoice[];
  can_generate_report: boolean;
  chapter_progress?: {
    completed_chapters: string[];
    current_chapter: string | null;
    current_chapters: string[];
    locked_chapters: string[];
    total_stages: number;
  };
}

export interface PersonaData {
  display_name: string;
  profile: Record<string, string>;
  impression: string;
  tags: string[];
  layer0: string[];
  layer2: {
    tone: string;
    patterns: string[];
    voice_sample: string;
    emotional_tells: string;
    speaking_pace: string;
  };
  layer3: {
    priorities: string;
    enthusiasm: string[];
    caution: string[];
  };
  layer5: {
    excited_by: string[];
    avoids: string[];
    dislikes: string[];
  };
  personality_traits: Record<string, number>;
}

export interface VnChoice {
  option_key: string;
  text: string;
  affection_target: string;
}

export interface VnScene {
  completed: boolean;
  session_id: string;
  choice_id?: string;
  chapter?: string;
  title: string;
  location: string;
  mood: string;
  speaker: string;
  speaker_slug?: string;
  speaker_source_name?: string;
  narrator_text: string;
  character_text: string;
  characters?: string[];
  source_characters?: string[];
  character_identities?: { source_name: string; slug: string; display_name: string }[];
  choices: VnChoice[];
  ai_generated: boolean;
  skill_driven?: boolean;
  asset_strategy?: string;
  background_asset?: { url: string; alt?: string; source?: string } | null;
  character_asset?: { url: string; alt?: string; source?: string } | null;
  skill_enrichment?: Record<string, PersonaData>;
  recent_choices?: RecentChoice[];
  current_route?: string | null;
}

export interface LocalGameInfo {
  game_path?: string;
  game_info?: {
    valid?: boolean;
    found_files?: string[];
    found_dirs?: string[];
    integration_mode?: string;
  };
}

export type ValidationResult = {
  valid?: boolean;
  path?: string;
  found_files?: string[];
  missing_files?: string[];
  found_dirs?: string[];
  hint?: string;
  skill_count?: number;
  integration_mode?: string;
  capabilities?: string[];
  asset_summary?: {
    generated_backgrounds?: number;
    generated_characters?: number;
    fallback_backgrounds?: number;
    fallback_sprites?: number;
  };
};

export type PersonaOverview = {
  count?: number;
  personas?: Record<string, { display_name?: string; profile?: Record<string, string> }>;
};

// Boundary for later measurement API embedding: the VN UI only needs these callbacks.
export interface SenrenMeasurementBridge {
  startSession: (mode: Exclude<SenrenMode, "" | "local">) => Promise<void>;
  startLocalGame: () => Promise<void>;
  validateGamePath: () => Promise<void>;
  submitChoice: (choice: VnChoice) => Promise<void>;
  goToReport: () => void;
  leaveSession: () => void;
}

export interface SenrenGameScreenProps {
  scene: VnScene;
  liveState: LiveState | null;
  mode: SenrenMode;
  gamePath: string;
  localGameInfo: LocalGameInfo | null;
  personas: Record<string, PersonaData>;
  displayedText: string;
  typing: boolean;
  autoMode: boolean;
  hidden: boolean;
  submitting: boolean;
  error: string;
  showLog: boolean;
  showSkills: boolean;
  showWorkbench: boolean;
  onFinishTyping: () => void;
  onSubmitChoice: (choice: VnChoice) => Promise<void> | void;
  onToggleAuto: () => void;
  onSetHidden: (value: boolean) => void;
  onSetShowLog: (value: boolean) => void;
  onSetShowSkills: (value: boolean) => void;
  onSetShowWorkbench: (value: boolean) => void;
  onExit: () => void;
  onReport: () => void;
}
