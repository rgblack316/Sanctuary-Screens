import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";

const HEX = /^#[0-9a-fA-F]{6}$/;

export const ColorField = ({ label, value, onChange, testid }) => {
  const [text, setText] = useState(value);
  useEffect(() => setText(value), [value]);
  return (
    <label className="flex items-center gap-3" data-testid={`${testid}-field`}>
      <input
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value.toUpperCase())}
        data-testid={`${testid}-picker`}
        className="h-10 w-12 cursor-pointer rounded-md border border-[#2A3550] bg-transparent p-1"
      />
      <span className="flex-1 text-sm text-slate-300">{label}</span>
      <Input
        value={text}
        maxLength={7}
        onChange={(e) => {
          const v = e.target.value.trim();
          setText(v);
          if (HEX.test(v)) onChange(v.toUpperCase());
        }}
        data-testid={`${testid}-hex`}
        className={`h-9 w-28 bg-[#0B0E14] font-mono-ui text-xs ${HEX.test(text) ? "" : "border-rose-500"}`}
      />
    </label>
  );
};

export const RangeField = ({ label, value, onChange, min, max, step = 1, unit = "", testid, disabled }) => (
  <div className={disabled ? "opacity-40" : ""} data-testid={`${testid}-field`}>
    <div className="mb-2 flex items-center justify-between text-sm">
      <span className="text-slate-300">{label}</span>
      <span className="font-mono-ui text-xs text-slate-400" data-testid={`${testid}-value`}>{value}{unit}</span>
    </div>
    <Slider value={[value]} min={min} max={max} step={step} disabled={disabled} onValueChange={([v]) => onChange(v)} data-testid={`${testid}-slider`} />
  </div>
);
