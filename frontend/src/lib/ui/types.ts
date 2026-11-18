export interface SelectOption<T> {
	value: T;
	label: string;
	/** Non-selectable group heading the option is listed under */
	group?: string;
	/** Color dot in front of the entry */
	color?: string;
	/** Small grey hint text on the right */
	hint?: string;
	/** Render indented (e.g. a subcategory below a selectable main category) */
	indent?: boolean;
	disabled?: boolean;
}
