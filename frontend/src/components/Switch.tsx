interface SwitchProps {
  checked: boolean;
  onChange?: (checked: boolean) => void;
}

export default function Switch({ checked, onChange }: SwitchProps) {
  return (
    <label className="switch">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange?.(e.target.checked)}
      />
      <span className="track">
        <span className="thumb" />
      </span>
    </label>
  );
}
