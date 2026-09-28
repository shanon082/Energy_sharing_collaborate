import {isAuth} from "@/actions/is-auth"
import { useEffect, useState } from "react";

export const useAuth = () => {
   
  
    const [auth, setAuth] = useState<boolean>(false)
    
    const [loading, setLoading] = useState(false);
  
  
  
    useEffect(() => {
  
      setLoading(true);
  
      isAuth().then((response) => {
        if(response.auth){
  
          setAuth(() => true)
        } else {
          setAuth(() => false)
        }
  
        setLoading(false)
      }).catch(error => {
        setLoading(false)
        setAuth(() => false)
      })
  
    }, [])
  
    return {auth, loading};
  };