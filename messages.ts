/**
 * Central user-facing messages. Loaded from messages.json at repo root (process.cwd() when run from root).
 * Use msg.key or substitute(msg.key, { param: value }).
 */
import fs from "fs";
import path from "path";

const messagesPath = path.join(process.cwd(), "messages.json");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const raw: Record<string, any> = JSON.parse(fs.readFileSync(messagesPath, "utf-8"));

export const msg = raw as {
  nervous_system: {
    hardware_table_title: string;
    hardware_table_sep: string;
    hardware_table_header: string;
    header: string;
    eyes_listening: string;
    eyes_restarted: string;
    matter_lobe_enabled: string;
    chip_tool_belly: string;
    head_touch_error: string;
    belly_touch_error: string;
    vibration_error: string;
    matter_disabled: string;
    belly_cycling: string;
    head_touch: string;
    shiver: string;
    matter_startup_logs_header: string;
    touch_event_driven: string;
    touch_polling: string;
    matter_lobe_prefix: string;
    motion_detected: string;
    motion_clear: string;
    motion_sleep: string;
    motion_event_driven: string;
    motion_sensor_enabled: string;
    eyes_full_reinit_trigger: string;
  };
  matter_lobe: {
    status: {
      initializing: string;
      checking_port: string;
      port_free: string;
      node_created: string;
      endpoints_ready: string;
      online: string;
    };
    udp_port_in_use: string;
    onoff_changed: string;
    brightness_set: string;
    xy_x_set: string;
    xy_y_set: string;
    hue_set: string;
    identify_received: string;
    switch_featuremap_warn: string;
    broadcasting: string;
    identify_on: string;
    status_order: string[];
    ready_for_initial_pairing: string;
    multi_admin_opening: string;
  };
  eye_bridge: { error: string };
  touch: {
    head_touch_gpio_error: string;
    belly_touch_gpio_error: string;
    vibration_gpio_error: string;
  };
  audio: { aplay_failed: string };
  eyes: {
    display_init_failed: string;
    udp_bind: string;
    opening_animated: string;
    animation: string;
    eye_shape: string;
    eye_type: string;
  };
};

/** Replace {key} in template with params[key]. */
export function substitute(template: string, params: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key) => String(params[key] ?? ""));
}
