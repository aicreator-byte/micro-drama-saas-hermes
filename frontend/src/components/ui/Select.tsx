'use client';

import {
  SelectHTMLAttributes,
  forwardRef,
  createContext,
  useContext,
  useState,
  useRef,
  useEffect,
  ReactNode,
} from 'react';
import { cn } from '@/lib/utils';

interface SelectOption {
  value: string;
  label: string;
}

// Native select wrapper (for scenes page)
interface NativeSelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  helperText?: string;
  options: SelectOption[];
  placeholder?: string;
}

export const NativeSelect = forwardRef<HTMLSelectElement, NativeSelectProps>(
  ({ className, label, error, helperText, options, placeholder, id, ...props }, ref) => {
    const selectId = id || label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className="w-full">
        {label && (
          <label htmlFor={selectId} className="block text-sm font-medium text-gray-700 mb-1.5">
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={cn(
            'w-full px-3 py-2 border rounded-lg shadow-sm transition-colors bg-white',
            'focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500',
            'disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed',
            error
              ? 'border-red-300 text-red-900 focus:ring-red-500 focus:border-red-500'
              : 'border-gray-300 text-gray-900',
            className
          )}
          aria-invalid={error ? 'true' : 'false'}
          aria-describedby={error ? `${selectId}-error` : helperText ? `${selectId}-helper` : undefined}
          {...props}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {error && (
          <p id={`${selectId}-error`} className="mt-1.5 text-sm text-red-600" role="alert">
            {error}
          </p>
        )}
        {helperText && !error && (
          <p id={`${selectId}-helper`} className="mt-1.5 text-sm text-gray-500">
            {helperText}
          </p>
        )}
      </div>
    );
  }
);

NativeSelect.displayName = 'NativeSelect';

// Radix-style Select components (for prompts, flow, assets, dialogues pages)
interface SelectContextValue {
  value: string;
  onValueChange: (value: string) => void;
  disabled?: boolean;
}

const SelectContext = createContext<SelectContextValue | null>(null);

interface SelectRootProps {
  value?: string;
  onValueChange?: (value: string) => void;
  defaultValue?: string;
  disabled?: boolean;
  children: ReactNode;
  placeholder?: string;
}

function SelectRootComponent({
  value: controlledValue,
  onValueChange,
  defaultValue = '',
  disabled,
  children,
}: SelectRootProps) {
  const [uncontrolledValue, setUncontrolledValue] = useState(defaultValue);
  const isControlled = controlledValue !== undefined;
  const value = isControlled ? controlledValue : uncontrolledValue;

  const handleValueChange = (newValue: string) => {
    if (!isControlled) {
      setUncontrolledValue(newValue);
    }
    onValueChange?.(newValue);
  };

  return (
    <SelectContext.Provider value={{ value, onValueChange: handleValueChange, disabled }}>
      {children}
    </SelectContext.Provider>
  );
}

interface SelectTriggerProps {
  className?: string;
  children?: ReactNode;
  'aria-label'?: string;
}

function SelectTriggerComponent({ className, children, 'aria-label': ariaLabel, ...props }: SelectTriggerProps) {
  const context = useContext(SelectContext);
  if (!context) {
    throw new Error('SelectTrigger must be used within Select');
  }
  const { value, onValueChange, disabled } = context;

  const triggerRef = useRef<HTMLButtonElement>(null);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (triggerRef.current && !triggerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  return (
    <button
      ref={triggerRef}
      type="button"
      role="combobox"
      aria-expanded={isOpen}
      aria-haspopup="listbox"
      aria-label={ariaLabel}
      disabled={disabled}
      className={cn(
        'w-full px-3 py-2 border border-gray-300 rounded-lg bg-white',
        'focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500',
        'disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed',
        'flex items-center justify-between text-left',
        className
      )}
      onClick={() => !disabled && setIsOpen(!isOpen)}
      {...props}
    >
      <span className="truncate flex-1">
        {children || (value ? String(value) : 'Select...')}
      </span>
      <svg
        className={cn('w-4 h-4 text-gray-500 flex-shrink-0 ml-2 transition-transform', isOpen && 'rotate-180')}
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      </svg>
    </button>
  );
}

interface SelectValueProps {
  placeholder?: string;
  children?: ReactNode;
}

function SelectValueComponent({ placeholder, children }: SelectValueProps) {
  const context = useContext(SelectContext);
  if (!context) {
    throw new Error('SelectValue must be used within Select');
  }
  const { value } = context;

  return <span className={cn('text-gray-900', !value && 'text-gray-500')}>{children || value || placeholder}</span>;
}

interface SelectContentProps {
  className?: string;
  children: ReactNode;
  position?: 'popper' | 'item-aligned';
}

function SelectContentComponent({ className, children, position = 'popper' }: SelectContentProps) {
  const context = useContext(SelectContext);
  if (!context) {
    throw new Error('SelectContent must be used within Select');
  }

  return (
    <div
      className={cn(
        'absolute z-50 w-full max-h-60 overflow-auto rounded-lg border border-gray-300 bg-white shadow-lg',
        'mt-1 py-1 text-sm',
        className
      )}
      role="listbox"
      aria-orientation="vertical"
    >
      {children}
    </div>
  );
}

interface SelectItemProps {
  value: string;
  className?: string;
  children: ReactNode;
  disabled?: boolean;
}

const SelectItemComponent = forwardRef<HTMLDivElement, SelectItemProps>(
  ({ value, className, children, disabled, ...props }, ref) => {
    const context = useContext(SelectContext);
    if (!context) {
      throw new Error('SelectItem must be used within Select');
    }
    const { value: selectedValue, onValueChange } = context;
    const isSelected = selectedValue === value;

    return (
      <div
        ref={ref}
        role="option"
        aria-selected={isSelected}
        aria-disabled={disabled}
        data-value={value}
        className={cn(
          'px-3 py-2 cursor-pointer select-none relative',
          'hover:bg-purple-50 hover:text-purple-900',
          'focus:outline-none focus:bg-purple-50 focus:text-purple-900',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          isSelected && 'bg-purple-50 text-purple-900 font-medium',
          className
        )}
        onClick={() => !disabled && onValueChange(value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            !disabled && onValueChange(value);
          }
        }}
        tabIndex={disabled ? -1 : 0}
        {...props}
      >
        {children}
        {isSelected && (
          <svg
            className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-purple-600"
            fill="currentColor"
            viewBox="0 0 20 20"
            aria-hidden="true"
          >
            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
          </svg>
        )}
      </div>
    );
  }
);
SelectItemComponent.displayName = 'SelectItem';

// Export with the names that pages expect
export const Select = SelectRootComponent;
export const SelectTrigger = SelectTriggerComponent;
export const SelectValue = SelectValueComponent;
export const SelectContent = SelectContentComponent;
export const SelectItem = SelectItemComponent;