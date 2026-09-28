import { Country } from "./country.interface"

export type Profile = {
    email_verified: boolean,
    phone_verified: boolean,
    id_verified: boolean,
    country: Country
}