/**
 * Declaration for @matter/types so dynamic import resolves on Pi/strict resolution
 * when the package's exports don't expose types (TS7016).
 */
declare module "@matter/types" {
	export type DeviceTypeId = number & { readonly __brand: "DeviceTypeId" };
	export type VendorId = number & { readonly __brand: "VendorId" };
	export function DeviceTypeId(
		deviceTypeId: number,
		validate?: boolean,
	): DeviceTypeId;
	export function VendorId(vendorId: number, validate?: boolean): VendorId;
}
