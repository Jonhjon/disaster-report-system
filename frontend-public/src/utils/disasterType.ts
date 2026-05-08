import type { DisasterType } from "../types";
import { DISASTER_TYPE_LABELS } from "../types";

const _validDisasterTypes = Object.keys(DISASTER_TYPE_LABELS) as ReadonlyArray<string>;

export function isDisasterType(value: string): value is DisasterType {
  return _validDisasterTypes.includes(value);
}
