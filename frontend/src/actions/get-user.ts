"use server"

import { User } from "@/interface/user.interface"
import { getUserConfig } from "@/lib/account"
export const getUser = async () => {
    const user = await getUserConfig<User>()
    if(user){
        return user
    }
    return null
}