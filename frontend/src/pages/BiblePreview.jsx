import { BibleScreen } from "@/components/live/BibleScreen";

// Shows exactly what the admin has loaded but not yet sent to /bible (same look as the live display).
export default function BiblePreview() {
  return <BibleScreen channel="preview" />;
}
