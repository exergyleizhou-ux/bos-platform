import client from "@/api/client";
import type { BOSV9RCManifestResponse } from "@/types/governance";

export const governanceApi = {
  getRCManifest: async (): Promise<BOSV9RCManifestResponse> => {
    const { data } = await client.get<BOSV9RCManifestResponse>("/governance/rc-manifest");
    return data;
  },
};
