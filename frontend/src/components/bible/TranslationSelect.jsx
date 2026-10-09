import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const TranslationSelect = ({ translations, value, onChange, testid, className = "", disabled }) => (
  <Select value={value || undefined} onValueChange={onChange} disabled={disabled || translations.length === 0}>
    <SelectTrigger data-testid={testid} className={`h-11 bg-[#0B0E14] ${className}`}>
      <SelectValue placeholder="Translation" />
    </SelectTrigger>
    <SelectContent>
      {translations.map((t) => (
        <SelectItem key={t.translation_code} value={t.translation_code} data-testid={`${testid}-option-${t.translation_code}`}>
          {t.translation_code} · {t.translation_name}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
);
