"use server"

import authenticated from "@/lib/authenticated"

export const isAuth = async () => {
    if(await authenticated()){
        return {auth: true}
    }
    return {auth: false}
}